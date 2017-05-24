"""
Plot slices from joint analysis files.

Usage:
    plot_slices.py join <base_path>
    plot_slices.py <files>... [options]

Options:
    --output=<output>  Output directory; if blank a guess based on likely case name will be made
    --fields=<fields>  Comma separated list of fields to plot [default: s',enstrophy]
"""
import numpy as np

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import brewer2mpl
import matplotlib.colors as mcolors

from tools import analysis

import logging
logger = logging.getLogger(__name__.split('.')[-1])

class Colortable():
    def __init__(self, field,
                 reverse_scale=True, float_scale=False, logscale=False,
                 color_map=None):
        
        self.special_norm=False

        if color_map is None:
            if field=='enstrophy':
                self.color_map = ('BuPu', 'sequential', 9)
            else:
                self.color_map = ('RdYlBu', 'diverging', 11)
        else:
            self.color_map = color_map
            
        self.reverse_scale = reverse_scale
        self.float_scale = float_scale
        self.logscale = logscale

        self.cmap = brewer2mpl.get_map(*self.color_map, reverse=self.reverse_scale).mpl_colormap
        #self.cmap = plt.cm.get_cmap('inferno')
        if field=="s'":
            # build our own colormap, combining an existing one with two hsv ramps
            colors2 = np.flipud(plt.cm.RdYlBu(np.linspace(0, 1, 256)))
            hsv_mid = mcolors.rgb_to_hsv(colors2[:,0:3])
            
            n_hsv=256
            hsv = np.zeros((n_hsv,3))
            hsv_target = [0.7, 0.25, 1]
            print("HSV blue start: {:5.2f} {:5.2f} {:5.2f}".format(hsv_mid[0,0],hsv_mid[0,1],hsv_mid[0,2]))
            print("HSV blue end  : {:5.2f} {:5.2f} {:5.2f}".format(hsv_target[0],hsv_target[1],hsv_target[2]))

            hsv[:,0] = np.linspace(hsv_target[0], hsv_mid[0,0], n_hsv)
            hsv[:,1] = np.linspace(hsv_target[1], hsv_mid[0,1], n_hsv)
            hsv[:,2] = np.linspace(hsv_target[2], hsv_mid[0,2], n_hsv)
            colors1 = np.ones((n_hsv, 4))
            colors1[:,0:3] = mcolors.hsv_to_rgb(hsv)
            
            n_hsv=256
            hsv = np.zeros((n_hsv,3))
            hsv_target = [1, 0.25, 1]
            print("HSV red  start: {:5.2f} {:5.2f} {:5.2f}".format(hsv_mid[-1,0],hsv_mid[-1,1],hsv_mid[-1,2]))
            print("HSV red  end  : {:5.2f} {:5.2f} {:5.2f}".format(hsv_target[0],hsv_target[1],hsv_target[2]))

            hsv[:,0] = np.linspace(hsv_mid[-1,0], hsv_target[0], n_hsv)
            hsv[:,1] = np.linspace(hsv_mid[-1,1], hsv_target[1], n_hsv)
            hsv[:,2] = np.linspace(hsv_mid[-1,2], hsv_target[2], n_hsv)
            colors3 = np.ones((n_hsv, 4))
            colors3[:,0:3] = mcolors.hsv_to_rgb(hsv)


            # combine them and build a new colormap
            colors = np.vstack((colors1, colors2, colors3))
            self.special_norm=True
            self.cmap = mcolors.LinearSegmentedColormap.from_list('three_map', colors)

    class Normalize(mcolors.Normalize):
        def __init__(self, vmin=None, vmax=None, match1=None, match2=None, clip=False):
            self.match1 = match1
            self.match2 = match2
            mcolors.Normalize.__init__(self, vmin, vmax, clip)

        def __call__(self, value, clip=None):
            x, y = [self.vmin, self.match1, self.match2, self.vmax], [0, 0.25, 0.75, 1]
            return np.ma.masked_array(np.interp(value, x, y))
        
class ImageStack():
    def __init__(self, x, y, fields, field_names,
                 true_aspect_ratio=True, vertical_stack=True, scale=3.0,
                 verbose=True, percent_cut=0.1, **kwargs):

        self.verbose=verbose
        
        # Storage
        images = []
        image_axes = []
        cbar_axes = []

        # Determine grid size
        if vertical_stack:
            nrows = len(fields)
            ncols = 1
        else:
            nrows = 1
            ncols = len(fields)

        # Setup spacing [top, bottom, left, right] and [height, width]
        t_mar, b_mar, l_mar, r_mar = (0.2, 0.2, 0.2, 0.2)
        t_pad, b_pad, l_pad, r_pad = (0.15, 0.03, 0.03, 0.03)
        h_cbar, w_cbar = (0.05, 1.)

        domain_width = np.max(x)-np.min(x)
        domain_height = np.max(y)-np.min(y)
        if true_aspect_ratio:
          h_data, w_data = (1., domain_width/domain_height)
        else:
          h_data, w_data = (1., 1.)

        h_im = t_pad + h_cbar + h_data + b_pad
        w_im = l_pad + w_data + r_pad
        h_total = t_mar + nrows * h_im + b_mar
        w_total = l_mar + ncols * w_im + r_mar

        self.dpi_png = int(max(150, len(x)/(w_total*scale)))
        if self.verbose:
            logger.info("figure size is {:g}x{:g} at {} dpi".format(scale * w_total, scale * h_total, self.dpi_png))
            logger.info("     and in px {:g}x{:g}".format(scale * w_total*self.dpi_png, scale * h_total*self.dpi_png))
        # Create figure and axes
        self.fig = fig = plt.figure(1, figsize=(scale * w_total,
                                                scale * h_total))
        row = 0
        cindex = 0

        for j, field in enumerate(fields):
            field_name = field_names[j]
            
            left = (l_mar + w_im * cindex + l_pad) / w_total
            bottom = 1 - (t_mar + h_im * (row + 1) - b_pad) / h_total
            width = w_data / w_total
            height = h_data / h_total
            imax = fig.add_axes([left, bottom, width, height])
            image_axes.append(imax)
            image_axes[j].lastrow = (row == nrows - 1)
            image_axes[j].firstcol = (cindex == 0)

            left = (l_mar + w_im * cindex + l_pad) / w_total
            bottom = 1 - (t_mar + h_im * row + t_pad + h_cbar) / h_total
            width = w_cbar / w_total
            height = h_cbar / h_total
            cbax = fig.add_axes([left, bottom, width, height])
            cbar_axes.append(cbax)

            cindex+=1
            if cindex%ncols == 0:
                # wrap around and start the next row
                row += 1
                cindex = 0

            image = Image(field_name,imax,cbax, **kwargs)
            static_min, static_max = image.get_scale(field, percent_cut=percent_cut)
            cz_min, cz_max = image.get_scale(field[:,np.int(field.shape[-1]/2):], percent_cut=0.5*percent_cut)
            if np.abs(cz_min) > np.abs(static_min):
                static_min, static_max = image.get_scale(field, percent_cut=percent_cut)
                cz_min, cz_max = image.get_scale(field[:,0:np.int(field.shape[-1]/2)], percent_cut=0.25*percent_cut, even_scale=True)
                
            def order_values(a,b):
                if np.abs(a) > np.abs(b):
                    temp_storage = a
                    a = b
                    b = temp_storage
                return a,b
            
            cz_min,static_min = order_values(cz_min, static_min)
            cz_max,static_max = order_values(cz_max, static_max)
            
            image.add_image(fig,x,y,field.T,
                            cz_scale=(cz_min, cz_max),
                            ct_scale=(static_min, static_max))
            
            image.set_scale(static_min, static_max)

            images.append(image)
            
        # Title
        height = 1 - (0.6 * t_mar) / h_total
        self.timestring = fig.suptitle(r'', y=height, size=16)

        self.images = images
        
        # Set up images and labels        
        #
        ##     images[j].set_clim(static_min, static_max)
        ##     print(fname, ": +- ", -static_min, static_max)

    def update(self, fields):
        for i, image in enumerate(self.images):
            image.update_image(fields[i].T)
            
    def write(self, data_dir, name, i_fig):
        logger.debug("png size: {}".format(self.fig.get_size_inches()*self.fig.dpi))
        figure_file = "{:s}/{:s}_{:06d}.png".format(data_dir,name,i_fig)
        self.fig.savefig(figure_file, dpi=self.dpi_png)
        logger.info("writting {:s}".format(figure_file))

    def close(self):
        plt.close(self.fig)
        
class Image():
    def __init__(self, field_name, imax, cbax,
                 xstr='x/H', ystr='z/H',
                 static_scale = True, float_scale=False, fixed_lim=None, even_scale=False, units=True,
                 **kwargs):

        self.xstr = xstr
        self.ystr = ystr

        self.imax = imax
        self.cbax = cbax
        
        self.field_name = field_name
        self.float_scale = float_scale
        self.fixed_lim = fixed_lim
        self.even_scale = even_scale
        self.static_scale = static_scale
        
        self.units = units
        
        self.set_colortable(**kwargs)
        self.add_labels(self.field_name)

    def set_colortable(self, **kwargs):
        self.colortable = Colortable(self.field_name, **kwargs)

    def add_labels(self, fname):
        imax = self.imax
        cbax = self.cbax
        
        # Title
        title = imax.set_title('{:s}'.format(fname), size=14)
        title.set_y(1.1)

        # Colorbar
        self.cbax.xaxis.set_ticks_position('top')
        plt.setp(cbax.get_xticklabels(), size=10)

        if imax.lastrow:
            imax.set_xlabel(self.xstr, size=12)
            plt.setp(imax.get_xticklabels(), size=10)
        else:
            plt.setp(imax.get_xticklabels(), visible=False)

        if imax.firstcol:
            self.imax.set_ylabel(self.ystr, size=12)
            plt.setp(imax.get_yticklabels(), size=10)
        else:
            plt.setp(imax.get_yticklabels(), visible=False)
             
    def create_limits_mesh(self, x, y):
        xd = np.diff(x)
        yd = np.diff(y)
        shape = x.shape
        xm = np.zeros((y.size+1, x.size+1))
        ym = np.zeros((y.size+1, x.size+1))
        xm[:, 0] = x[0] - xd[0] / 2.
        xm[:, 1:-1] = x[:-1] + xd / 2.
        xm[:, -1] = x[-1] + xd[-1] / 2.
        ym[0, :] = y[0] - yd[0] / 2.
        ym[1:-1, :] = (y[:-1] + yd / 2.)[:, None]
        ym[-1, :] = y[-1] + yd[-1] / 2.

        return xm, ym
           
    def add_image(self, fig, x, y, data, cz_scale=None, ct_scale=None):
        imax = self.imax
        cbax = self.cbax
        cmap = self.colortable.cmap
        
        if self.units:
            xm, ym = self.create_limits_mesh(x, y)

            if self.colortable.special_norm:
                cz_min, cz_max = cz_scale
                im = imax.pcolormesh(xm, ym, data, cmap=cmap, zorder=1, norm=self.colortable.Normalize(match1=cz_min, match2=cz_max))
            else:
                im = imax.pcolormesh(xm, ym, data, cmap=cmap, zorder=1)
            plot_extent = [xm.min(), xm.max(), ym.min(), ym.max()]                
            imax.axis(plot_extent)
            
        else:
            im = imax.imshow(data, zorder=1, aspect='auto',
                             interpolation='none', origin='lower',
                             cmap=cmap)
            shape = data.shape
            plot_extent = [-0.5, shape[1] - 0.5, -0.5, shape[0] - 0.5]
            imax.axis(plot_extent)

        if self.colortable.special_norm:
            cz_min, cz_max = cz_scale
            ct_min, ct_max = self.get_scale(data)
            print("image min/max {} {}".format(ct_min, ct_max))
            boundaries=np.hstack([np.linspace(ct_min, cz_min, 100),
                                  np.linspace(cz_min, cz_max, 100),
                                  np.linspace(cz_max, ct_max, 100)])
            locs = [ct_min, cz_min, 0, cz_max, ct_max]
            ticks=ticker.FixedLocator(locs)
            #ticks=ticker.MaxNLocator(nbins=5, prune='both')
            cb = fig.colorbar(im, cax=cbax, orientation='horizontal',
                              ticks=ticks, norm=self.colortable.Normalize(match1=cz_min, match2=cz_max),
                              spacing='proportional', boundaries=boundaries)
        else:
            cb = fig.colorbar(im, cax=cbax, orientation='horizontal',
                              ticks=ticker.MaxNLocator(nbins=5, prune='both'),  spacing='proportional')

        cb.formatter.set_powerlimits((4, 3))
        cb.ax.tick_params(axis='x',direction='in',labeltop='on')
        cb.ax.tick_params(axis='x',direction='in',labelbottom='off')
        cb.update_ticks()
        self.im = im

    def set_limits(self, x_limits, y_limits):
        plot_extent = [x_limits[0], x_limits[1], y_limits[0], y_limits[1]]                
        self.imax.axis(plot_extent)
        
    def update_image(self, data):
        im = self.im
        
        if self.units:
            im.set_array(np.ravel(data))
        else:
            im.set_data(data)

        #if not self.static_scale or self.float_scale:
        #image_min, image_max = self.get_scale(data, fixed_lim=self.fixed_lim, even_scale=self.even_scale)
        

    def percent_trim(self, data, percent_cut=0.1):
        if isinstance(percent_cut, list):
            if len(percent_cut) > 1:
                low_percent_cut  = percent_cut[0]
                high_percent_cut = percent_cut[1]
            else:
                low_percent_cut  = percent_cut[0]
                high_percent_cut = percent_cut[0]
        else:
            low_percent_cut  = percent_cut
            high_percent_cut = percent_cut

        # trimming method from Ben's ASH analysis package
        sorted_data = np.sort(data, axis=None)
        N_elements = len(sorted_data)
        min_value = sorted_data[np.int(np.ceil(low_percent_cut*N_elements))]
        max_value = sorted_data[np.int(np.floor((1-high_percent_cut)*N_elements-1))]
        return min_value, max_value

    def set_scale(self, image_min, image_max):
        self.im.set_clim(image_min, image_max)
        
    def get_scale(self, field, fixed_lim=None, even_scale=None, percent_cut=0.03):
        if even_scale is None:
            even_scale = self.even_scale
        if fixed_lim is None:
            fixed_lim = self.fixed_lim
            
        if fixed_lim is None:
            if even_scale:
                image_min, image_max = self.percent_trim(field, percent_cut=percent_cut)
                if np.abs(image_min) > image_max:
                    image_max = np.abs(image_min)
                elif image_min < 0:
                    image_min = -np.abs(image_max)
            else:
                image_min, image_max = self.percent_trim(field, percent_cut=percent_cut)
        else:
            image_min = fixed_lim[0]
            image_max = fixed_lim[1]

        return image_min, image_max

    

def main(files, fields, output_path='./', output_name='snapshot', static_scale=False, profile_files=None):
    from mpi4py import MPI

    comm_world = MPI.COMM_WORLD
    rank = comm_world.rank
    size = comm_world.size
    
    data = analysis.Slice(files)
    
    # select down to the data you wish to plot
    data_list = []
    for field in fields:
        logger.info(data.data[field].shape)
        data_list.append(data.data[field][0,:])
        
    imagestack = ImageStack(data.x, data.z, data_list, fields)

    scale_late = True
    if static_scale:
        for i, image in enumerate(imagestack.images):
            static_min, static_max = image.get_scale(data_list[i], percent_cut=0.1)
            print(static_min, static_max)
            if scale_late:
                static_min = comm_world.scatter([static_min]*size,root = size-1)
                static_max = comm_world.scatter([static_max]*size,root = size-1)
            else:
                static_min = comm_world.scatter([static_min]*size,root = 0)
                static_max = comm_world.scatter([static_max]*size,root = 0)
            print("post comm: {}--{}".format(static_min, static_max))
            image.set_scale(static_min, static_max)
              
    for i, time in enumerate(data.times):
        current_data = []
        for field in fields:
            current_data.append(data.data[field][i,:])
                    
        imagestack.update(current_data)
        if not static_scale:
            for i_im, image in enumerate(imagestack.images):
                image.set_scale(*image.get_scale(current_data[i_im]))
                                                      
        i_fig = data.writes[i]
        # Update time title
        tstr = 't = {:6.3e}'.format(time)
        imagestack.timestring.set_text(tstr)
        imagestack.write(output_path, output_name, i_fig)
        imagestack.close()


if __name__ == "__main__":

    import pathlib
    from docopt import docopt
    from dedalus.tools import logging
    from dedalus.tools import post
    from dedalus.tools.parallel import Sync

    args = docopt(__doc__)
    if args['join']:
        post.merge_analysis(args['<base_path>'])
    else:
        if args['--output'] is not None:
            output_path = pathlib.Path(args['--output']).absolute()
        else:
            data_dir = args['<files>'][0].split('/')[0]
            data_dir += '/'
            output_path = pathlib.Path(data_dir).absolute()
        # Create output directory if needed
        with Sync() as sync:
            if sync.comm.rank == 0:
                if not output_path.exists():
                    output_path.mkdir()
        fields = args['--fields'].split(',')
        logger.info("output to {}".format(output_path))
        
        def accumulate_files(filename,start,count,file_list):
            #print(filename, start, count)
            if start==0:
                file_list.append(filename)
            
        file_list = []
        post.visit_writes(args['<files>'],  accumulate_files, file_list=file_list)
        #print(file_list)
        if len(file_list) > 0:
            main(file_list, fields, output_path=str(output_path)+'/')


