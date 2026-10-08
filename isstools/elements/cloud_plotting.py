from xas.xasproject import XASDataSet
from xas.file_io import load_binned_df_from_file
import numpy as np
from matplotlib import pyplot as plt

def generate_output_figures(filepath, imagepath=None, t_flag=True, f_flag=True, r_flag=True):
    plt.ioff()
    df, header = load_binned_df_from_file(filepath)
    df = df.sort_values('energy')

    energy = np.array(df['energy'])
    mu_t = np.array(np.log(df['i0']/df['it']))
    mu_f = np.array(df['iff']/df['i0'])
    mu_r = np.array(np.log(df['it']/df['ir']))
    try:
        ds_t = XASDataSet(name=filepath, md={}, energy=energy, mu=mu_t, filename=filepath, datatype='experiment')
    except:
        ds_t = None
    try:
        ds_f = XASDataSet(name=filepath, md={}, energy=energy, mu=mu_f, filename=filepath, datatype='experiment')
    except:
        ds_f = None
    try:
        ds_r = XASDataSet(name=filepath, md={}, energy=energy, mu=mu_r, filename=filepath, datatype='experiment')
    except:
        ds_r = None


    fig, ((ax1, ax2, ax3), (ax4, ax5, ax6), (ax7, ax8, ax9)) = plt.subplots(3, 3, figsize=(12, 9))
    fig.set_tight_layout(True)

    ax_e = (ax1, ax2, ax3, ax4, ax5, ax6)
    ax_k = (ax7, ax8, ax9)
    ax_mu_raw = (ax1, ax2, ax3)
    ax_mu_flat = (ax4, ax5, ax6)
    ax_chi = (ax7, ax8, ax9)

    if t_flag:
        plot_xas_raw(energy, mu_t, ax1, color='b')
        plot_xas_in_E(ds_t, ax4, color='b')
        plot_xas_in_K(ds_t, ax7, color='b')

    if f_flag:
        plot_xas_raw(energy, mu_f, ax2, color='r')
        plot_xas_in_E(ds_f, ax5, color='r')
        plot_xas_in_K(ds_f, ax8, color='r')

    if r_flag:
        plot_xas_raw(energy, mu_r, ax3, color='k')
        plot_xas_in_E(ds_r, ax6, color='k')
        plot_xas_in_K(ds_r, ax9, color='k')


    for ax in ax_e:
        ax.set_xlabel('E, eV')
        ax.set_xlim(energy[0], energy[-1])
    for ax in ax_k:
        ax.set_xlabel('k, A$^{-1}$')
        if ds_t:
            ax.set_xlim(ds_t.k[0], ds_t.k[-1])
    for ax in ax_mu_raw:
        ax.set_ylabel('mu')
    for ax in ax_mu_flat:
        ax.set_ylabel('mu norm')
    for ax in ax_chi:
        ax.set_ylabel(r'$\chi$(k) * k$^{2}$')

    ax1.set_title('Transmission')
    ax2.set_title('Fluorescence')
    ax3.set_title('Reference')


    # legend = []

    #
    #
    # ax1.legend(legend)
    #
    # ax1.set_xlabel('E, eV')
    # ax1.set_ylabel('norm/flat mu')
    # ax3.set_xlabel('E, eV')
    # ax3.set_ylabel('norm/flat mu')
    # ax5.set_xlabel('E, eV')
    # ax5.set_ylabel('norm/flat mu')
    #
    # ax2.set_xlabel('k, A$^{-1}$')
    # ax2.set_ylabel('$\chi$(k) * k$^{2}$')
    # ax4.set_xlabel('k, A$^{-1}$')
    # ax4.set_ylabel('$\chi$(k) * k$^{2}$')
    # ax5.set_xlabel('k, A$^{-1}$')
    # ax6.set_ylabel('$\chi$(k) * k$^{2}$')

    # plt.tight_layout()
    if imagepath:
        plt.savefig(imagepath, dpi=300)
    plt.ion()
    plt.close(fig)


def plot_xas_raw(e, mu, ax, color):
    ax.plot(e, mu, color=color)


def plot_xas_in_E(ds, ax, color):
    if ds:
        ds.normalize_force()
        ax.plot(ds.energy, ds.flat, color=color)


def plot_xas_in_K(ds, ax, color):
    if ds:
        ds.extract_chi_force()
        ax.plot(ds.k, ds.chi * ds.k**2, color=color)
