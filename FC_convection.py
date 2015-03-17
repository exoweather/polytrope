import numpy as np
import time
import os
import sys
import equations

#import matplotlib.pyplot as plt

import logging
logger = logging.getLogger(__name__)

from dedalus.public import *
from dedalus.tools  import post
from dedalus.extras import flow_tools
from dedalus.extras.checkpointing import Checkpoint

initial_time = time.time()

logger.info("Starting Dedalus script {:s}".format(sys.argv[0]))

# save data in directory named after script
data_dir = sys.argv[0].split('.py')[0]+'/'

Rayleigh = 4e4
Prandtl = 1

# Set domain
Lz = 100
Lx = 3*Lz

nx = 96
nz = 96

atmosphere = equations.FC_polytrope(nx=nx, nz=nz, Lx=Lx, Lz=Lz)
atmosphere.set_IVP_problem(Rayleigh, Prandtl)
atmosphere.set_BC()
problem = atmosphere.get_problem()

if atmosphere.domain.distributor.rank == 0:
    if not os.path.exists('{:s}/'.format(data_dir)):
        os.mkdir('{:s}/'.format(data_dir))

ts = timesteppers.RK443
cfl_safety_factor = 0.2*4

# Build solver
solver = problem.build_solver(ts)

x = atmosphere.domain.grid(0)
z = atmosphere.domain.grid(1)


# initial conditions
u = solver.state['u']
w = solver.state['w']
T = solver.state['T1']
s = solver.state['s']
ln_rho = solver.state['ln_rho1']

solver.evaluator.vars['Lx'] = Lx
solver.evaluator.vars['Lz'] = Lz

A0 = 1e-6
np.random.seed(1+atmosphere.domain.distributor.rank)

T.set_scales(atmosphere.domain.dealias, keep_data=True)
z_dealias = atmosphere.domain.grid(axis=1, scales=atmosphere.domain.dealias)
T['g'] = A0*np.sin(np.pi*z_dealias/Lz)*np.random.randn(*T['g'].shape)*atmosphere.T0['g']

logger.info("A0 = {:g}".format(A0))
logger.info("T = {:g} -- {:g}".format(np.min(T['g']), np.max(T['g'])))

logger.info("thermal_time = {:g}, top_thermal_time = {:g}".format(atmosphere.thermal_time, atmosphere.top_thermal_time))


max_dt = atmosphere.buoyancy_time

report_cadence = 1
output_time_cadence = 0.1*atmosphere.buoyancy_time
solver.stop_sim_time = 0.25*atmosphere.thermal_time
solver.stop_iteration= 100 #np.inf
solver.stop_wall_time = 0.25*3600

logger.info("output cadence = {:g}".format(output_time_cadence))

analysis_slice = solver.evaluator.add_file_handler(data_dir+"slices", sim_dt=output_time_cadence, max_writes=20, parallel=False)

analysis_slice.add_task("s", name="s")
analysis_slice.add_task("s - integ(s, 'x')/Lx", name="s'")
analysis_slice.add_task("u", name="u")
analysis_slice.add_task("w", name="w")
analysis_slice.add_task("(dx(w) - dz(u))**2", name="enstrophy")

analysis_profile = solver.evaluator.add_file_handler(data_dir+"profiles", sim_dt=output_time_cadence, max_writes=20, parallel=False)

analysis_scalar = solver.evaluator.add_file_handler(data_dir+"scalar", sim_dt=output_time_cadence, max_writes=20, parallel=False)
analysis_scalar.add_task("integ(1/2*rho0*exp(ln_rho1)*(u**2+w**2))/Lx/Lz", name="KE")
analysis_scalar.add_task("integ(rho0*exp(ln_rho1)*phi)/Lx/Lz", name="PE")
analysis_scalar.add_task("integ(rho0*exp(ln_rho1)*Cv*T)/Lx/Lz", name="IE")
analysis_scalar.add_task("integ(1/2*rho0*exp(ln_rho1)*(u**2+w**2)+rho0*exp(ln_rho1)*phi+rho0*exp(ln_rho1)*Cv*T)/Lx/Lz", name="TE")
analysis_scalar.add_task("integ(sqrt(u**2))/Lx/Lz", name="u_rms")
analysis_scalar.add_task("integ(sqrt(w**2))/Lx/Lz", name="w_rms")
analysis_scalar.add_task("integ(sqrt(u**2+w**2)*Lz/nu)/Lx/Lz", name="Re_rms")
analysis_scalar.add_task("integ(sqrt(u**2+w**2)*Lz/chi)/Lx/Lz", name="Pe_rms")

do_checkpointing=True
if do_checkpointing:
    checkpoint = Checkpoint(data_dir)
    checkpoint.set_checkpoint(solver, iter=20)


    
cfl_cadence = 1
CFL = flow_tools.CFL(solver, initial_dt=max_dt, cadence=cfl_cadence, safety=cfl_safety_factor,
                     max_change=1.5, min_change=0.5, max_dt=max_dt)

CFL.add_velocities(('u', 'w'))

# Flow properties
flow = flow_tools.GlobalFlowProperty(solver, cadence=1)
flow.add_property("sqrt(u*u + w*w)*Lz/ nu", name='Re')


start_time = time.time()
while solver.ok:

    dt = CFL.compute_dt()
    # advance
    solver.step(dt)
        
    # update lists
    if solver.iteration % report_cadence == 0:
        log_string = 'Iteration: {:5d}, Time: {:8.3e}, dt: {:8.3e}, Re: {:8.3e}/{:8.3e}'.format(solver.iteration, solver.sim_time, dt,
                                                                                                flow.grid_average('Re'), flow.max('Re'))
        logger.info(log_string)
        
end_time = time.time()

# Print statistics
elapsed_time = end_time - start_time
elapsed_sim_time = solver.sim_time
N_iterations = solver.iteration 
logger.info('main loop time: {:e}'.format(elapsed_time))
logger.info('Iterations: {:d}'.format(N_iterations))
logger.info('iter/sec: {:g}'.format(N_iterations/(elapsed_time)))
logger.info('Average timestep: {:e}'.format(elapsed_sim_time / N_iterations))

logger.info('beginning join operation')
if do_checkpointing:
    logger.info(data_dir+'/checkpoint/')
    post.merge_analysis(data_dir+'/checkpoint/')
logger.info(analysis_slice.base_path)
post.merge_analysis(analysis_slice.base_path)

if (atmosphere.domain.distributor.rank==0):

    N_TOTAL_CPU = atmosphere.domain.distributor.comm_world.size
    
    # Print statistics
    print('-' * 40)
    total_time = end_time-initial_time
    main_loop_time = end_time - start_time
    startup_time = start_time-initial_time
    n_steps = solver.iteration-1
    print('  startup time:', startup_time)
    print('main loop time:', main_loop_time)
    print('    total time:', total_time)
    print('Iterations:', solver.iteration)
    print('Average timestep:', solver.sim_time / n_steps)
    print("          N_cores, Nx, Nz, startup     main loop,   main loop/iter, main loop/iter/grid, n_cores*main loop/iter/grid")
    print('scaling:',
          ' {:d} {:d} {:d}'.format(N_TOTAL_CPU,nx,nz),
          ' {:8.3g} {:8.3g} {:8.3g} {:8.3g} {:8.3g}'.format(startup_time,
                                                            main_loop_time, 
                                                            main_loop_time/n_steps, 
                                                            main_loop_time/n_steps/(nx*nz), 
                                                            N_TOTAL_CPU*main_loop_time/n_steps/(nx*nz)))
    print('-' * 40)

