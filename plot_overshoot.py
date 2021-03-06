"""
Plot overshoot from joint analysis files.

Usage:
    plot_overshoot.py [options]

Options:
    --output=<output>  Output directory [default: ./]
    --verbose          Make diagnostic plots of each sim
"""
import numpy as np
from tools.analysis import interp_bisect_root

from collections import OrderedDict

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from cycler import cycler

import logging
logger = logging.getLogger(__name__.split('.')[-1])

from tools import analysis

def plot_diagnostics(z, norm_diag, roots, output_path='/.', boundary=None):
    figs = {}
    apjfig = analysis.APJSingleColumnFigure()

    min_plot = 1
    max_plot = np.log(5) # half a log-space unit above 1
    plot_floor = 1e-7

    for key in norm_diag:
        color = next(apjfig.ax._get_lines.prop_cycler)['color']
        
        analysis.semilogy_posneg(apjfig.ax, z, norm_diag[key][1], label=norm_diag[key][0], color=color)

        apjfig.ax.axvline(x=roots[key], linestyle='dotted', color=color)
        min_plot = min(min_plot, np.min(np.abs(norm_diag[key][1])))
        logger.debug("{} : {} : {}".format(key, norm_diag[key][0], norm_diag[key][1]))
    min_plot = max(plot_floor, min_plot)

    #apjfig.ax.axhline(y=1e-2, color='black', linestyle='dashed')
    #apjfig.ax.axhline(y=1e-4, color='black', linestyle='dashed')
    if boundary is not None:
        apjfig.ax.axvline(x=boundary, color='black', linestyle='dotted')
    apjfig.legend(loc="upper left", title="normalized by max", fontsize=6)
    apjfig.ax.set_xlabel("z")
    apjfig.ax.set_ylabel("overshoot diagnostics")
    apjfig.ax.set_ylim(min_plot, max_plot)
    padding = 0.1*np.max(z)
    xmin = np.min(z) - padding
    xmax = np.max(z) + padding
    apjfig.ax.set_xlim(xmin, xmax)
    figs["diagnostics"]=apjfig

    for key in figs.keys():
        figs[key].savefig(output_path+'overshoot_{}.png'.format(key), dpi=600)

def plot_overshoot_times(times, overshoot, average_overshoot=None, output_path='./'):
    apjfig = analysis.APJSingleColumnFigure()
    ref = 'grad_s_mean'
    ref_depth = overshoot[ref]
    min_z = 100
    max_z = 0

    logger.info("overshoot locations with time (reference depth = {})".format(ref))
    logger.info("{:12s} : {}".format(ref, ref_depth))
    for key in overshoot:
        if key!=ref and key!='grad_s':
            color = next(apjfig.ax._get_lines.prop_cycler)['color']
            #logger.info("{:10s} -- OV: {}".format(key, ref_depth - overshoot[key]))
            logger.info("{:12s} : {}".format(key, overshoot[key]))
            q = overshoot[key] #np.abs(overshoot[key]-ref_depth)
            apjfig.ax.plot(times, q, label=key, color=color)
            if average_overshoot is not None:
                apjfig.ax.axhline(average_overshoot[key], linestyle='dashed', color=color)
            min_z = min(min_z, np.min(q))
            max_z = max(max_z, np.max(q))

    min_z = min(min_z, np.min(ref_depth))
    max_z = max(max_z, np.max(ref_depth))
    apjfig.ax.plot(times, ref_depth, label='BCZ', linestyle='dashed', color='black')
    
    z_pad = 0.01*max_z
    apjfig.ax.set_ylim(min_z-z_pad, max_z+z_pad)
    apjfig.legend(loc="upper right", title="diagnostics", fontsize=6)
    apjfig.ax.set_xlabel("time")
    apjfig.ax.set_ylabel("$z_o$ of overshoot")
    apjfig.savefig(output_path+"overshoot_timetrace.png", dpi=600)

    logger.info("y-lims for overshoot_times: {} -- {}".format(min_z-z_pad, max_z+z_pad))

            
def diagnose_overshoot(averages, z, stiffness, boundary=None, output_path='./', verbose=False):

    def norm(f):
        return f/np.max(np.abs(f))

    norm_diag = OrderedDict()

    norm_diag['grad_s_mean'] = (r'$\nabla (s_0)$', norm(averages['grad_s_mean']))
    norm_diag['grad_s_tot'] = (r'$\nabla (s_0 + s_1)$', norm(averages['grad_s_tot']))
    norm_diag['brunt'] = (r'$\omega^2/N^2$', norm(averages['enstrophy'] - averages['brunt_squared_tot']))
    norm_diag['s_mean'] = (r'$s_0$', norm(averages['s_mean']))
    norm_diag['s_tot'] = (r'$s_0+s_1$', norm(averages['s_tot']))

    stiff_threshold = stiffness**(-0.5)

    norm_diag['s_fluc_std'] = (r'$\delta(s_1)$', norm(averages['s_fluc_std']))
    #stiff_threshold = np.max(norm(averages['s_fluc_std'])) # max value
    #logger.info("std dev thresh: {}".format(stiff_threshold))
        
    # estimate penetration depths
    overshoot_depths = OrderedDict()
    
    linear_root_quantities = ['KE_flux', 'grad_s_mean', 'grad_s_tot', 's_mean', 's_tot', 'brunt']
    entropy_quantities = ['s_mean', 's_tot']
    for key in norm_diag:
        if key in linear_root_quantities:
            threshold = 0
            if key in entropy_quantities:
                # grab the top of the atmosphere value
                threshold = norm_diag[key][1][-1]
                
            criteria = norm_diag[key][1] - threshold

        else:
            threshold = stiff_threshold
            criteria = np.log(norm_diag[key][1])-np.log(threshold)
            
        logger.debug("key: {} has threshold {}".format(key, threshold))
        
        z_search = np.copy(z)
        criteria_search = np.copy(criteria)
        a = None
        b = None

        if key=='grad_s_mean':
            a = np.min(z)
            b = np.max(z)
        elif key=='s_tot':
            a = np.min(z)

        z_root = interp_bisect_root(z_search, criteria_search, a=a, b=b)
 
        overshoot_depths[key] = z_root
        
        logger.debug("  bisect: {:>10s} : found root z={}".format(key, z_root))

    if verbose:
        logger.info("Plotting diagnostics in {}".format(output_path))
        plot_diagnostics(z, norm_diag, overshoot_depths, output_path=output_path)
        
    return overshoot_depths

def overshoot_time_trace(averages, z, times, stiffness, average_overshoot=None, output_path='./'):
    single_time = OrderedDict()
    overshoot_depths = OrderedDict()
    for i, time in enumerate(times):
        for key in averages:
            single_time[key] = averages[key][i,0,:]
        single_overshoot_depths = diagnose_overshoot(single_time, z, stiffness)
        if i == 0:
            for key in single_overshoot_depths:
                overshoot_depths[key] = single_overshoot_depths[key]
        else:
            for key in single_overshoot_depths:
                overshoot_depths[key] = np.append(overshoot_depths[key], single_overshoot_depths[key])
                
    plot_overshoot_times(times, overshoot_depths, average_overshoot=average_overshoot, output_path=output_path)

    std_dev = OrderedDict()
    avgs = OrderedDict()
    for key in overshoot_depths:
        std_dev[key] = np.std(overshoot_depths[key])
        avgs[key] = np.mean(overshoot_depths[key])

    return avgs, std_dev
    
def analyze_case(files, verbose=False, output_path=None):
    import re
    
    data = analysis.Profile(files)
    logger.debug("read in data from {}".format(data.files))

    averages = data.average
    std_devs = data.std_dev
    times = data.times
    z = data.z
    delta_t = times[-1]-times[0]
    logger.info("Averaged over interval t = {:g} -- {:g} for total delta_t = {:g}".format(times[0], times[-1], delta_t))
    if output_path is None:
        import pathlib
        data_dir = files[0].split('/')[0]
        data_dir += '/'
        output_path = pathlib.Path(data_dir).absolute()

    stiffness_string = re.search(r'_S\d+e\d+', '{:}'.format(files)).group()
    stiffness = float(stiffness_string.split('_S')[1])
    rayleigh_string = re.search(r'_Ra\d+e\d+', '{:}'.format(files)).group()
    rayleigh = float(rayleigh_string.split('_Ra')[1])
    erf_string = re.search(r'_erf\d+.\d+', '{:}'.format(files))
    if erf_string is None:
        erf = 0.128
    else:
        erf = float(erf_string.group().split('_erf')[1])
        
    logger.info("overshoot: case has stiffness of {}".format(stiffness))
    
    overshoot_depths = diagnose_overshoot(averages, z, stiffness, output_path=str(output_path)+'/', verbose=verbose)

    logger.info("overshoot in time-averaged profile")
    for key in overshoot_depths:
        logger.info("{:12s} --> z={}".format(key, overshoot_depths[key]))

    if verbose:
        avgs, std_dev = overshoot_time_trace(data.data, z, times, stiffness, average_overshoot=overshoot_depths, output_path=str(output_path)+'/')
    else:
        std_dev = OrderedDict()
        for key in overshoot_depths:
            std_dev[key] = np.nan
    
    return overshoot_depths, std_dev

def analyze_all_cases(stiffness_file_list, **kwargs):
    overshoot = OrderedDict()
    std_dev   = OrderedDict()
    first_run = True
    
    for stiffness, files in stiffness_file_list:
        overshoot_one_case, std_dev_one_case = analyze_case(files, **kwargs)
        for key in overshoot_one_case:
            if first_run:
                overshoot[key] = np.array(overshoot_one_case[key])
                std_dev[key]   = np.array(std_dev_one_case[key])
            else:
                overshoot[key] = np.append(overshoot[key], overshoot_one_case[key])
                std_dev[key]   = np.append(std_dev[key], std_dev_one_case[key])
                
        if first_run:
            stiffness_array = np.array(stiffness)
            first_run = False
        else:
            stiffness_array = np.append(stiffness_array, stiffness)
            
    return stiffness_array, overshoot, std_dev
    

def plot_overshoot(stiffness, overshoot, std_dev, output_path='./', linear=False, fig=None, marker='o'):

    if linear:
        x = 1/stiffness
    else:
        x = stiffness
        
    if fig is None:
        apjfig = analysis.APJSingleColumnFigure()
        min_z = 100
        max_z = 0
    else:
        logger.info("Appending to figure")
        apjfig = fig
        apjfig.ax.set_prop_cycle(None) 
        min_z, max_z = apjfig.ax.get_ylim()
        
    ref = 'grad_s_mean'
    compare = 'brunt'
    ref_depth = overshoot[ref]

    m_ad = 1.5
    m_rz = 3
    m_cz = m_ad-(m_rz-m_ad)/stiffness
    # the following assume that T(ref_depth)=ref_depth (namely, grad_T=-1 and we're probably in the CZ)
    H_rho = (ref_depth/m_cz) # estimate for H_rho at ref depth; H_rho = (T/m_cz)
    n_rho = m_cz*np.log(ref_depth) # estimate for n_rho at ref depth
    logger.info("T={}".format(ref_depth))
    logger.info("m_cz={}".format(m_cz))
    logger.info("H_rho={}".format(H_rho))
    logger.info("n_rho={}".format(n_rho))
    
    
    logger.info("reference depth:")
    logger.info("{} -- {}".format(ref, ref_depth))

    for key in overshoot:
        if key!=ref and key!='grad_s':
            color = next(apjfig.ax._get_lines.prop_cycler)['color']
            logger.info("{:10s} -- OV: {} ({})".format(key, ref_depth - overshoot[key],
                                                       (ref_depth - overshoot[key])/(ref_depth-overshoot[compare])))
            q = np.abs(overshoot[key]-ref_depth)            
            q = q/H_rho
            
            if np.any(np.isfinite(std_dev[key])):
                apjfig.ax.errorbar(x, q, yerr=std_dev[key], label=key, marker=marker, color=color)
            else:
                apjfig.ax.plot(x, q, label=key, marker=marker, color=color)

            min_z = min(min_z, np.nanmin(q))
            max_z = max(max_z, np.nanmax(q))

            if key=='enstrophy':
                # powerlaw fitting to the lower stiffness regime
                ii = (stiffness < 1e4)
                a = np.polyfit(np.log(stiffness[ii]), np.log(q[ii]), deg=1)
                powerlaw_label = r'$\mathrm{S}^\mathrm{p}$'+', p={:6.3g}'.format(a[0])
                logger.info(a)
                apjfig.ax.plot(x, np.exp(a[1])*x**a[0], label=powerlaw_label, color=color, linestyle='dotted')
                logger.info("low stiffness fit: {}".format(a))

    # plot is now of delta_z/H_rho
    z_predicted = m_rz*(np.exp(n_rho/(m_cz*stiffness))-1)
    Lz_cz = np.exp(n_rho/m_cz)-1
    L_adjust = (ref_depth-Lz_cz)/H_rho
    z_total = z_predicted + L_adjust
    logger.info("z_predicted/H {}".format(z_predicted))
    logger.info("Lz_cz         {}".format(Lz_cz))
    logger.info("L_adjust/H    {}".format(L_adjust))
    logger.info("prediction  = {}".format(z_total))
    apjfig.ax.plot(x, z_total, label="prediction")


    if linear:
        apjfig.ax.set_xscale("linear")
        apjfig.ax.set_xlabel("Inverse stiffness 1/S")
        if fig is None:
            apjfig.legend(loc="lower right", title="diagnostics", fontsize=6)
    else:
        apjfig.ax.set_xscale("log", nonposx='clip')
        apjfig.ax.set_xlabel("Stiffness S")
        if fig is None:
            apjfig.legend(loc="lower left", title="diagnostics", fontsize=6)
            
    
    apjfig.ax.set_yscale("log", nonposy='clip')
    
    if fig is None:
        min_z = 0.5*min_z
        max_z = 1.5*max_z
        
    apjfig.ax.set_ylim(min_z, max_z)
    logger.info("plot lims {}--{}".format(min_z, max_z))
    
    apjfig.ax.set_ylabel(r"$\Delta z/H_{\rho}$ of overshoot")
#    if linear:
#        apjfig.savefig(output_path+"overshoot_linear.png", dpi=600)
#    else:
#        apjfig.savefig(output_path+"overshoot.png", dpi=600)

    return apjfig
 
def main(output_path='./', **kwargs):
    import glob

    file_list =[(3e0, glob.glob('FC_multi_nrhocz3_Ra1e4_S3e0_single/profiles/profiles_s1[0,1,2,3,4]?.h5')),
                (1e1, glob.glob('FC_multi_nrhocz3_Ra1e4_S1e1_single/profiles/profiles_s1[0,1,2,3,4]?.h5')),
                (3e1, glob.glob('FC_multi_nrhocz3_Ra1e4_S3e1_single/profiles/profiles_s1[0,1,2,3,4]?.h5')),
                (1e2, glob.glob('FC_multi_nrhocz3_Ra1e4_S1e2_single/profiles/profiles_s1[0,1,2,3,4]?.h5')),
                (1e3, glob.glob('FC_multi_nrhocz3_Ra1e4_S1e3_single/profiles/profiles_s1[0,1,2,3,4]?.h5')),
                (1e4, glob.glob('FC_multi_nrhocz3_Ra1e4_S1e4_single/profiles/profiles_s1[0,1,2,3,4]?.h5'))]

    stiffness, overshoot, std_dev = analyze_all_cases(file_list, **kwargs)
    
    fig_linear = plot_overshoot(stiffness, overshoot, std_dev, output_path=output_path, linear=True)
    fig = plot_overshoot(stiffness, overshoot, std_dev, output_path=output_path)

    file_list =[(3e0, glob.glob('FC_multi_nrhocz3_Ra1e6_S3e0_single/profiles/profiles_s1[0,1,2,3,4]?.h5')),
                (1e1, glob.glob('FC_multi_nrhocz3_Ra1e6_S1e1_single/profiles/profiles_s1[0,1,2,3,4]?.h5')),
                (3e1, glob.glob('FC_multi_nrhocz3_Ra1e6_S3e1_single/profiles/profiles_s1[0,1,2,3,4]?.h5')),
                (1e2, glob.glob('FC_multi_nrhocz3_Ra1e6_S1e2_single/profiles/profiles_s1[0,1,2,3,4]?.h5')),
                (1e3, glob.glob('FC_multi_nrhocz3_Ra1e6_S1e3_single/profiles/profiles_s1[0,1,2,3,4]?.h5')),
                (1e4, glob.glob('FC_multi_nrhocz3_Ra1e6_S1e4_single/profiles/profiles_s1[0,1,2,3,4]?.h5'))]

    stiffness, overshoot, std_dev = analyze_all_cases(file_list, **kwargs)

    fig_linear = plot_overshoot(stiffness, overshoot, std_dev, output_path=output_path, linear=True, fig=fig_linear, marker='s')
    fig = plot_overshoot(stiffness, overshoot, std_dev, output_path=output_path, fig=fig, marker='s')


    file_list =[(1e1, glob.glob('FC_multi_nrhocz3_Ra1e8_S1e1_single/profiles/profiles_s[5,6,7]?.h5')),
                (3e1, glob.glob('FC_multi_nrhocz3_Ra1e8_S3e1_single/profiles/profiles_s[5,6,7]?.h5')),
                (1e2, glob.glob('FC_multi_nrhocz3_Ra1e8_S1e2_single/profiles/profiles_s[5,6,7]?.h5')),
                (1e3, glob.glob('FC_multi_nrhocz3_Ra1e8_S1e2_single/profiles/profiles_s[5,6,7]?.h5'))]


    stiffness, overshoot, std_dev = analyze_all_cases(file_list, **kwargs)

    fig_linear = plot_overshoot(stiffness, overshoot, std_dev, output_path=output_path, linear=True, fig=fig_linear, marker='*')
    fig = plot_overshoot(stiffness, overshoot, std_dev, output_path=output_path, fig=fig, marker='*')

    file_list =[(1e2, glob.glob('FC_multi_nrhocz3_Ra1e6_S1e2_erf0.05_single/profiles/profiles_s[5]?.h5')),
                (1e2, glob.glob('FC_multi_nrhocz3_Ra1e6_S1e2_single/profiles/profiles_s[5]?.h5'))]

    stiffness, overshoot, std_dev = analyze_all_cases(file_list, **kwargs)

    fig_linear = plot_overshoot(stiffness, overshoot, std_dev, output_path=output_path, linear=True, fig=fig_linear, marker='<')
    fig = plot_overshoot(stiffness, overshoot, std_dev, output_path=output_path, fig=fig, marker='<')


    file_list =[(1e2, glob.glob('FC_multi_nrhocz3_Ra1e4_S1e2_erf0.05_single/profiles/profiles_s[5]?.h5')),
                (1e2, glob.glob('FC_multi_nrhocz3_Ra1e4_S1e2_single/profiles/profiles_s[5]?.h5'))]

    stiffness, overshoot, std_dev = analyze_all_cases(file_list, **kwargs)

    fig_linear = plot_overshoot(stiffness, overshoot, std_dev, output_path=output_path, linear=True, fig=fig_linear, marker='>')
    fig = plot_overshoot(stiffness, overshoot, std_dev, output_path=output_path, fig=fig, marker='>')


    fig_linear.savefig(output_path+"overshoot_linear.png", dpi=600)
    fig.savefig(output_path+"overshoot.png", dpi=600)

     
if __name__ == "__main__":

    import pathlib
    from docopt import docopt
    from dedalus.tools import logging
    from dedalus.tools import post
    from dedalus.tools.parallel import Sync

    args = docopt(__doc__)

    output_path = pathlib.Path(args['--output']).absolute()
    # Create output directory if needed
    with Sync() as sync:
        if sync.comm.rank == 0:
            if not output_path.exists():
                output_path.mkdir()
    logger.info("output to {}".format(output_path))
    main(output_path=str(output_path)+'/', verbose=args['--verbose'])


