#!/usr/bin/env python3
"""
pyCrust_Mars

Create a crustal thickness map of Mars from gravity and topography.

This script generates two different crustal thickness maps. The first assumes
that the density of both the crust and mantle are constant, whereas the second
includes the effect of different densities on either side of the dichotomy
boundary. The average crustal thickness is iterated in order to obtain
a specified minimum crustal thickness.
"""
import numpy as np

import pyshtools

import pyMoho
from Hydrostatic import HydrostaticShapeLith
from Hydrostatic import HydrostaticShape
from ReadRefModel import ReadRefModel

# ==== MAIN FUNCTION ====


def main():

    gravfile = 'Data/gmm3_120_sha.tab'
    topofile = 'Data/MarsTopo719.shape'
    densityfile = 'Data/dichotomy_359.sh'

    model_name = ['DWThot', 'DWThotCrust1', 'DWThotCrust1r', 'EH45Tcold',
                  'EH45TcoldCrust1', 'EH45TcoldCrust1r', 'EH45ThotCrust2',
                  'EH45ThotCrust2r', 'LFAK', 'SANAK', 'TAYAK', 'DWAK',
                  'ZG_DW']
    spec = 'Data/Mars-reference-interior-models/Smrekar/'
    interior_file = [spec + name + '.deck' for name in model_name]

    lmax_calc = 90
    lmax = lmax_calc * 4

    potential = pyshtools.SHGravCoeffs.from_file(gravfile, header_units='km')

    print('Gravity file = {:s}'.format(gravfile))
    print('Lmax of potential coefficients = {:d}'.format(potential.lmax))
    print('Reference radius (km) = {:f}'.format(potential.r0 / 1.e3))
    print('GM = {:e}\n'.format(potential.gm))

    topo = pyshtools.SHCoeffs.from_file(topofile, lmax=lmax)
    topo.r0 = topo.coeffs[0, 0, 0]

    print('Topography file = {:s}'.format(topofile))
    print('Lmax of topography coefficients = {:d}'.format(topo.lmax))
    print('Reference radius (km) = {:f}\n'.format(topo.r0 / 1.e3))

    density = pyshtools.SHCoeffs.from_file(densityfile, lmax=lmax)

    print('Lmax of density coefficients = {:d}\n'.format(density.lmax))

    lat_insight = 4.502384
    lon_insight = 135.623447

    filter = 1
    half = 50
    nmax = 7
    lmax_hydro = 15
    t0_sigma = 5.  # maximum difference between minimum crustal thickness
    omega = pyshtools.constant.omega_mars.value

    d_lith = 150.e3
    d_sigma = 45.e3

    t0 = 1.e3  # minimum crustal thickness
    model = 10  # identifier for the interior reference model

    # --- read 1D reference interior model ---

    radius, rho, i_crust, i_core, i_lith = ReadRefModel(
        interior_file[model], depth=d_lith, quiet=False)

    rho_mantle = rho[i_crust-1]
    rho_core = rho[i_core-1]
    n = len(radius) - 1
    r0_model = radius[n]

    # --- Compute gravity contribution from hydrostatic density interfaces ---

    thickave = 44.e3  # initial guess of average crustal thickness
    r_sigma = topo.r0 - thickave
    rho_c = 2900.

    if True:
        # compute values for a planet that is completely fluid
        hlm_fluid, clm_fluid, mass_model = \
            HydrostaticShape(radius, rho, omega, potential.gm, potential.r0)
        print('--- Hydrostatic potential coefficients for a fluid planet ---')
        print('c20 = {:e}\nc40 = {:e}'.format(clm_fluid.coeffs[0, 2, 0],
                                              clm_fluid.coeffs[0, 4, 0]))
        print('--- Hydrostatic relief of surface for a fluid planet ---')
        print('h20 = {:e}\nh40 = {:e}'.format(hlm_fluid[n].coeffs[0, 2, 0],
                                              hlm_fluid[n].coeffs[0, 4, 0]))

    hlm, clm_hydro, mass_model = \
        HydrostaticShapeLith(radius, rho, i_lith, potential, topo, rho_c,
                             r_sigma, omega, lmax_hydro)

    print('Total mass of model (kg) = {:e}'.format(mass_model))
    print('% of J2 arising from beneath lithosphere = {:f}'
          .format(clm_hydro.coeffs[0, 2, 0]/potential.coeffs[0, 2, 0] * 100.))

    potential.coeffs[:, :lmax_hydro+1, :lmax_hydro+1] -= \
        clm_hydro.coeffs[:, :lmax_hydro+1, :lmax_hydro+1]

    # --- Constant density model ---

    rho_c = 2900.
    print('-- Constant density model --\nrho_c = {:f}'.format(rho_c))

    tmin = 1.e9
    thickave = 44.e3    # initial guess of average crustal thickness

    while abs(tmin - t0) > t0_sigma:
        # iterate to fit assumed minimum crustal thickness

        moho = pyMoho.pyMoho(potential, topo, lmax, rho_c, rho_mantle,
                             thickave, filter_type=filter, half=half,
                             lmax_calc=lmax_calc, nmax=nmax, quiet=True)

        thick_grid = (topo.pad(lmax) - moho.pad(lmax)).expand(grid='DH2')
        print('Average crustal thickness (km) = {:f}'.format(thickave / 1.e3))
        print('Crustal thickness at InSight landing sites (km) = {:f}'
              .format((topo.pad(lmax) - moho.pad(lmax))
                      .expand(lat=lat_insight, lon=lon_insight) / 1.e3))
        tmin = thick_grid.min()
        tmax = thick_grid.max()
        print('Minimum thickness (km) = {:e}'.format(tmin / 1.e3))
        print('Maximum thickness (km) = {:e}'.format(tmax / 1.e3))
        thickave += t0 - tmin

    thick_grid.plot(show=False, fname='Thick-Mars-1.png')
    moho.plot_spectrum(show=False, fname='Moho-spectrum-Mars-1.png')

    # --- Model with variable density ---

    rho_south = 2900.
    rho_north = 2900.
    porosity = 0.0

    print('-- Variable density model ---\n' +
          'rho_south = {:f}\n'.format(rho_south) +
          'rho_north = {:f}'.format(rho_north))

    density = density * (rho_north - rho_south)
    density.coeffs[0, 0, 0] += rho_south

    tmin = 1.e9
    thickave = 44.e3    # initial guess of average crustal thickness

    while abs(tmin - t0) > t0_sigma:
        # iterate to fit assumed minimum crustal thickness

        moho = pyMoho.pyMohoRho(potential, topo, density, porosity, lmax,
                                rho_mantle, thickave, filter_type=filter,
                                half=half, lmax_calc=lmax_calc, quiet=True,
                                nmax=nmax)

        thick_grid = (topo.pad(lmax) - moho.pad(lmax)).expand(grid='DH2')
        print('Average crustal thickness (km) = {:e}'.format(thickave / 1.e3))
        print('Crustal thickness at InSight landing sites (km) = {:e}'
              .format((topo.pad(lmax) - moho.pad(lmax))
                      .expand(lat=lat_insight, lon=lon_insight) / 1.e3))
        tmin = thick_grid.data.min()
        tmax = thick_grid.data.max()
        print('Minimum thickness (km) = {:e}'.format(tmin / 1.e3))
        print('Maximum thickness (km) = {:e}'.format(tmax / 1.e3))
        thickave += t0 - tmin

    thick_grid.plot(show=False, fname='Thick-Mars-2.png')
    moho.plot_spectrum(show=False, fname='Moho-spectrum-Mars-2.png')


# ==== EXECUTE SCRIPT ====
if __name__ == "__main__":
    main()
