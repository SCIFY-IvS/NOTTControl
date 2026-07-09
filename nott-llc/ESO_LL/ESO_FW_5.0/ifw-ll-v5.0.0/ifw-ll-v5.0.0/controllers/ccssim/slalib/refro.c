#include "TcPch.h"
#pragma hdrstop

#include "slalib.h"
#include "slamac.h"

static void atmt ( double, double, double, double, double, double,
                   double, double, double, double, double, double,
                   double*, double*, double* );
static void atms ( double, double, double, double, double*, double* );

void slaRefro ( double zobs, double hm, double tk, double phpa,
                double rh, double wlfq, double phi, double tlr,
                double eps, double *ref )
/*
**  - - - - - - - - -
**   s l a R e f r o
**  - - - - - - - - -
**
**  Atmospheric refraction for radio and optical/IR wavelengths.
**
**  Given:
**    zobs    double  observed zenith distance of the source (radian)
**    hm      double  height of the observer above sea level (metre)
**    tk      double  ambient temperature at the observer (K)
**    phpa    double  pressure at the observer (hPa = millibar)
**    rh      double  relative humidity at the observer (range 0-1)
**    wlfq    double  wavelength (micron) or minus frequency (GHz)
**    phi     double  latitude of the observer (radian, astronomical)
**    tlr     double  tropospheric lapse rate (K/metre)
**    eps     double  precision required to terminate iteration (radian)
**
**  Returned (function value):
**            double  refraction: in vacuo ZD minus observed ZD (radian)
**
**  Notes:
**
**  1  A suggested value for the tlr argument, the tropospheric lapse
**     rate, is 0.0065 (the sign is ignored).  If studies of the local
**     atmosphere have been carried out and a better tlr value is
**     available, it is worth using.
**
**  2  A suggested value for the eps argument is 1e-8.  The result is
**     usually at least two orders of magnitude more computationally
**     precise than the supplied eps value, and the choice of eps value
**     has a large effect on computational speed, particularly for large
**     zenith distances.
**
**  3  The function computes the refraction for zenith distances up
**     to and a little beyond 90 deg (see Note 6) using the Biot-Auer-
**     Standish method (Young 2004) in the form given by Hohenkerk &
**     Sinclair (1985):  see Section 3.281 of the Explanatory Supplement
**     (1992).
**
**  4  The C code is based upon the Fortran optical/IR refraction
**     subroutine AREF of C.Hohenkerk (HMNAO, September 1984), with
**     extensions to support the radio case.  The following changes to
**     the original HMNAO optical/IR refraction algorithm have been
**     made:
**
**     .  The angle arguments have been changed to radians.
**
**     .  Any value of zobs is allowed (see Note 6, below).  Other
**        argument values have been limited to safe values.
**
**     .  Gas constants from Murray (1983) have been used.
**
**     .  A better model for Ps(T,P) has been adopted, taken from
**        Buck (1981).
**
**     .  The formula for the water vapour pressure, given the
**        saturation pressure and the relative humidity, is from
**        Equation 2.5.5 in Crane & Meeks (1976).
**
**     .  The IAG (1999) optical refractivity for dry air is used.
**
**     .  Provision for radio wavelengths has been added using
**        expressions originally devised by A.T.Sinclair, RGO (private
**        communication 1989).  The low frequency refractivity model
**        currently used is from Rueger (2002).  Corrections for O2 and
**        H2O features, important in the mm/submm region, are applied
**        using the MPM93 model of Liebe et al. (1993) as set out in
**        Fortran code N93AIR by Hufford & Liebe.  Ionospheric effects
**        are neglected, compromising accuracy below about 30 MHz.
**
**     .  The numerical integration phase has been rearranged for
**        extra clarity.
**
**     .  Various small changes have been made to gain speed.
**
**  5  The argument wlfq specifies whether optical or radio and the
**     wavelength/frequency.  Positive values specify wavelength in
**     microns and are the usual way of selecting the optical case.
**     Negative values specify frequency in GHz and are the usual way of
**     selecting the radio case.  The transition from optical to radio
**     is assumed to occur at 100 microns (about 3000 GHz).
**
**  6  Before use, the value of zobs is expressed in the range +/- pi.
**     If this ranged zobs is -ve, the result ref is computed from its
**     absolute value before being made negative to match.  In addition,
**     if it has an absolute value greater than 93 deg (optical/IR) or
**     90.5 deg (radio/mm/submm), the refraction for that angle is
**     returned, appropriately signed.  This precaution is necessary
**     because the integration fails when the ray curvature approaches
**     that of the Earth's surface.
**
**  7  As in the original Hohenkerk & Sinclair algorithm (see also
**     Sinclair 1982), fixed values of the water vapour polytrope
**     exponent, the height of the tropopause, and the height at which
**     refraction is negligible are used.
**
**  8  The optical refraction has been compared with the Pulkovo tables
**     (Abalakin 1985).  For the example provided in the Preface (p9),
**     the present function predicts refraction of 331.40 arcsec,
**     compared with the Pulkovo figure of 331.38 arcsec.  For the main
**     tables, the agreement over most of the range is within 0.03%;
**     for the extreme zenith distances 88, 89 and 90 deg, the Pulkovo
**     predictions are 1064.54, 1409.42 and 1977.97 arcsec, whereas
**     the present function returns values that are 0.07, 0.49 and
**     3.37 arcsec lower, respectively.
**
**     The radio refraction has been tested against work done by
**     Iain Coulson, JACH (private communication 1995) for the
**     James Clerk Maxwell Telescope, Mauna Kea.  For typical conditions,
**     agreement at the 0.1 arcsec level is achieved for moderate ZD,
**     worsening to perhaps 0.5-1.0 arcsec at ZD 80 deg.  At hot and
**     humid sea-level sites the agreement would not be as good.
**
**  9  It should be noted that the relative humidity rh is formally
**     defined in terms of "mixing ratio" rather than pressures or
**     densities as is often stated.  It is the mass of water per unit
**     mass of dry air divided by that for saturated air at the same
**     temperature and pressure (see Gill 1982).
**
**  10 The algorithm is designed for observers in the troposphere.  The
**     supplied temperature, pressure and lapse rate are assumed to be
**     for a point in the troposphere and are used to define a model
**     atmosphere with the tropopause at 11km altitude and a constant
**     temperature above that.  However, in practice, the refraction
**     values returned for stratospheric observers, at altitudes up to
**     25km, are quite usable.
**
**  Called:  slaDrange, atmt, atms
**
**  References:
**
**     Abalakin, V.K. (ed), "Refraction Tables of Pulkovo Observatory",
**     5th ed., Central Astronomical Observatory, Academy of Sciences
**     of the USSR:  Nauka Publishing House, Leningrad Section,
**     Leningrad, USSR, 1985.
**
**     Buck, A., "New Equations for Computing Vapor Pressure and
**     Enhancement Factor", J. Appl. Met., 20, 1527-1532, 1981.
**
**     Crane, R.K. & Meeks, M.L. (ed), "Refraction Effects in the
**     Neutral Atmosphere", Methods of Experimental Physics:
**     Astrophysics 12B, Academic Press, 1976.
**
**     Gill, A.E., "Atmosphere-Ocean Dynamics", Academic Press, 1982.
**
**     Hohenkerk, C.Y. & Sinclair, A.T., "The computation of angular
**     atmospheric refraction at large zenith angles", NAO Technical
**     Note No. 63, Royal Greenwich Observatory, 1985.
**
**     International Association of Geodesy, Resolution 3,
**     XXIInd General Assembly, Birmingham, UK, 1999.
**
**     Liebe, H.J., Hufford, G.A. & Cotton, M.G., "Propagation modeling
**     of moist air and suspended water/ice particles at frequencies
**     below 1000 GHz", in Proc. NATO/AGARD Wave Propagation Panel, 52nd
**     Meeting, Paper No. 3/1-10, Mallorca, Spain, May 1993.
**
**     Murray, C.A., Vectorial Astrometry, Adam Hilger, 1983.
**
**     Rueger, J.M., "Refractive Index Formulae for Electronic Distance
**     Measurement with Radio and Millimetre Waves", in Unisurv Report
**     S-68, School of Surveying and Spatial Information Systems,
**     University of New South Wales, Sydney, Australia, 2002.
**
**     Seidelmann, P.K. (ed), "Explanatory Supplement to the
**     Astronomical Almanac", University Science Books, 1992.
**
**     Sinclair, A.T., "The effect of atmospheric refraction on laser
**     ranging data", NAO Technical Note No. 59, Royal Greenwich
**     Observatory, 1982.
**
**     Young, A.T., "Sunset science. IV. Low-altitude refraction",
**     Astron. J., 127, 3622-3637, 2004.
**
**  Last revision:   20 May 2009
**
**  Copyright P.T.Wallace.  All rights reserved.
*/

/* Numerical integration: maximum number of strips. */
#define ISMAX 16384

/* The refraction integrand */
#define refi(DN,RDNDR) ((RDNDR)/(DN+RDNDR));

{
/* Maximum allowed zobs (radians) */
   const double zmaxo = 1.623156204; /* optical/IR:  93.0 degrees  */
   const double zmaxr = 1.579522973; /*      radio:  90.5 degrees  */

/* Other constants */
   const double c = 299792.458;    /* speed of light (km/s) */
   const double gcr = 8314.32;     /* universal gas constant       */
   const double dmd = 28.9644;     /* molecular weight of dry air  */
   const double dmw = 18.0152;     /* molecular weight of water
                                                            vapour */
   const double s = 6378120.0;     /* mean Earth radius (metre)    */
   const double delta = 18.36;     /* exponent of temperature
                                         dependence of water vapour
                                                          pressure */
   const double ht = 11000.0;      /* height of tropopause (metre) */
   const double hs = 80000.0;      /* upper limit for refractive
                                                       effects (m) */

/* Observer, atmosphere and refraction variables */
   double wl;       /* wavelength (microns) */
   double fq;       /* frequency (GHz) */
   double h0;       /* observer's height above sea level (m) */
   double t0;       /* ambient temperature (K) */
   double p0;       /* ambient air pressure (hPa) */
   double rh0;      /* ambient relative humidity (0-1) */
   double alpha;    /* tropospheric lapse rate (K/m) */
   double ps0;      /* ambient saturated water vapour pressure (hPa) */
   double pd0;      /* ambient dry air partial pressure (hPa) */
   double pw0;      /* ambient water vapour partial pressure (hPa) */
   double a,bw,cw;  /* refractivity coefficients */
   double gb;       /* g at centroid of vertical air column (m/s/s) */
   double gamal;    /* constant of the atmospheric model = g*Md/r */
   double gamma;    /* exponent of temperature dependence of pressure */
   double r0;       /* geocentre to observer (m) */
   double rt;       /* geocentre to tropopause (m) */
   double rs;       /* geocentre to top of stratosphere (m) */

   int opt, j, layer, is, n, i;
   double w, zobs1, zobs2, tol, tk2, tk3, tk4, e, znnx, znny, th, thsq,
          th1, thp8, q1, q2, q3, fj, x1, q, y1, qsq, x2, y2, agd, f,
          q2r, q4, q4r, t, dn, rdndr, sk0, f0, zt, ft, q5, q6, zts, fts,
          zs, fs, reft, refold, z0, zrange, fb, ff, r1, fo, fe, h, r,
          sz, dr, refp;

/* --------------------- */
/* Radio dispersion data */
/* --------------------- */

/* O2, nonresonant O2, H2O.  cf. Liebe et al. (1993) Tables 1 & 2. */

/* Line frequencies */
   double fl[] = {
      50.474238,  50.987749,  51.503350,  52.021410,  52.542394,
      53.066907,  53.595749,  54.130000,  54.671159,  55.221367,
      55.783802,  56.264775,  56.363389,  56.968206,  57.612484,
      58.323877,  58.446590,  59.164207,  59.590983,  60.306061,
      60.434776,  61.150560,  61.800154,  62.411215,  62.486260,
      62.997977,  63.568518,  64.127767,  64.678903,  65.224071,
      65.764772,  66.302091,  66.836830,  67.369598,  67.900867,
      68.431005,  68.960311, 118.750343,

     368.498350, 424.763124, 487.249370, 715.393150, 773.839675,
     834.145330,

      22.235080,  67.803960, 119.995940, 183.310091, 321.225644,
     325.152919, 336.222601, 380.197372, 390.134508, 437.346667,
     439.150812, 443.018295, 448.001075, 470.888947, 474.689127,
     488.491133, 503.568532, 504.482692, 547.676440, 552.020960,
     556.936002, 620.700807, 645.866155, 658.005280, 752.033227,
     841.053973, 859.962313, 899.306675, 902.616173, 906.207325,
     916.171582, 923.118427, 970.315022, 987.926764, 1780.00000 };

/* Strength coefficients */
   double a1[] = {
        0.094e-6,   0.246e-6,   0.608e-6,   1.414e-6,   3.102e-6,
        6.410e-6,  12.470e-6,  22.800e-6,  39.180e-6,  63.160e-6,
       95.350e-6,  54.890e-6, 134.400e-6, 176.300e-6, 214.100e-6,
      238.600e-6, 145.700e-6, 240.400e-6, 211.200e-6, 212.400e-6,
      246.100e-6, 250.400e-6, 229.800e-6, 193.300e-6, 151.700e-6,
      150.300e-6, 108.700e-6,  73.350e-6,  46.350e-6,  27.480e-6,
       15.300e-6,   8.009e-6,   3.946e-6,   1.832e-6,   0.801e-6,
        0.330e-6,   0.128e-6,  94.500e-6,

        6.790e-6,  63.800e-6,  23.500e-6,   9.960e-6,  67.100e-6,
       18.000e-6,

        0.1130e-1,  0.0012e-1,  0.0008e-1,  2.4200e-1,     0.0483e-1,
        1.4990e-1,  0.0011e-1, 11.5200e-1,  0.0046e-1,     0.0650e-1,
        0.9218e-1,  0.1976e-1, 10.3200e-1,  0.3297e-1,     1.2620e-1,
        0.2520e-1,  0.0390e-1,  0.0130e-1,  9.7010e-1,    14.7700e-1,
      487.4000e-1,  5.0120e-1,  0.0713e-1,  0.3022e-1,   239.6000e-1,
        0.0140e-1,  0.1472e-1,  0.0605e-1,  0.0426e-1,     0.1876e-1,
        8.3410e-1,  0.0869e-1,  8.9720e-1,132.1000e-1, 22300.0000e-1 };

   double a2[] = {
        9.694,      8.694,      7.744,      6.844,      6.004,
        5.224,      4.484,      3.814,      3.194,      2.624,
        2.119,      0.015,      1.660,      1.260,      0.915,
        0.626,      0.084,      0.391,      0.212,      0.212,
        0.391,      0.626,      0.915,      1.260,      0.083,
        1.665,      2.115,      2.620,      3.195,      3.815,
        4.485,      5.225,      6.005,      6.845,      7.745,
        8.695,      9.695,      0.009,

        0.049,      0.044,      0.049,      0.145,      0.130,
        0.147,

        2.143,      8.735,      8.356,      0.668,      6.181,
        1.540,      9.829,      1.048,      7.350,      5.050,
        3.596,      5.050,      1.405,      3.599,      2.381,
        2.853,      6.733,      6.733,      0.114,      0.114,
        0.159,      2.200,      8.580,      7.820,      0.396,
        8.180,      7.989,      7.917,      8.432,      5.111,
        1.442,     10.220,      1.920,      0.258,      0.952 };

/* Width coefficients */
   double a3[] = {
        0.890e-3,   0.910e-3,   0.940e-3,   0.970e-3,   0.990e-3,
        1.020e-3,   1.050e-3,   1.070e-3,   1.100e-3,   1.130e-3,
        1.170e-3,   1.730e-3,   1.200e-3,   1.240e-3,   1.280e-3,
        1.330e-3,   1.520e-3,   1.390e-3,   1.430e-3,   1.450e-3,
        1.360e-3,   1.310e-3,   1.270e-3,   1.230e-3,   1.540e-3,
        1.200e-3,   1.170e-3,   1.130e-3,   1.100e-3,   1.070e-3,
        1.050e-3,   1.020e-3,   0.990e-3,   0.970e-3,   0.940e-3,
        0.920e-3,   0.900e-3,   1.630e-3,

        1.920e-3,   1.930e-3,   1.920e-3,   1.810e-3,   1.810e-3,
        1.820e-3,

        2.811e-3,   2.858e-3,   2.948e-3,   3.050e-3,   2.303e-3,
        2.783e-3,   2.693e-3,   2.873e-3,   2.152e-3,   1.845e-3,
        2.100e-3,   1.860e-3,   2.632e-3,   2.152e-3,   2.355e-3,
        2.602e-3,   1.612e-3,   1.612e-3,   2.600e-3,   2.600e-3,
        3.210e-3,   2.438e-3,   1.800e-3,   3.210e-3,   3.060e-3,
        1.590e-3,   3.060e-3,   2.985e-3,   2.865e-3,   2.408e-3,
        2.670e-3,   2.900e-3,   2.550e-3,   2.985e-3,  17.620e-3 };

   double a4[] = {
        4.80,       4.93,       4.78,       5.30,       4.69,
        4.85,       4.74,       5.38,       4.81,       4.23,
        4.29,       4.23,       4.84,       4.57,       4.65,
        5.04,       3.98,       4.01,       4.50,       4.50,
        4.11,       4.68,       4.00,       4.14,       4.09,
        5.76,       4.09,       4.53,       5.10,       4.70,
        5.00,       4.78,       4.94,       4.55,      30.50 };

/* Overlap */
   double a5[] = {
        0.240e-3,   0.220e-3,   0.197e-3,   0.166e-3,   0.136e-3,
        0.131e-3,   0.230e-3,   0.335e-3,   0.374e-3,   0.258e-3,
       -0.166e-3,   0.390e-3,  -0.297e-3,  -0.416e-3,  -0.613e-3,
       -0.205e-3,   0.748e-3,  -0.722e-3,   0.765e-3,  -0.705e-3,
        0.697e-3,   0.104e-3,   0.570e-3,   0.360e-3,  -0.498e-3,
        0.239e-3,   0.108e-3,  -0.311e-3,  -0.421e-3,  -0.375e-3,
       -0.267e-3,  -0.168e-3,  -0.169e-3,  -0.200e-3,  -0.228e-3,
       -0.240e-3,  -0.250e-3,  -0.036e-3,

        0.0,        0.0,        0.0,        0.0,        0.0,
        0.0,

        0.69,       0.69,       0.70,       0.64,       0.67,
        0.68,       0.69,       0.54,       0.63,       0.60,
        0.63,       0.60,       0.66,       0.66,       0.65,
        0.69,       0.61,       0.61,       0.70,       0.70,
        0.69,       0.71,       0.60,       0.69,       0.68,
        0.33,       0.68,       0.68,       0.70,       0.70,
        0.70,       0.70,       0.64,       0.68,       2.00 };

   double a6[] = {
        0.790e-3,   0.780e-3,   0.774e-3,   0.764e-3,   0.751e-3,
        0.714e-3,   0.584e-3,   0.431e-3,   0.305e-3,   0.339e-3,
        0.705e-3,  -0.113e-3,   0.753e-3,   0.742e-3,   0.697e-3,
        0.051e-3,  -0.146e-3,   0.266e-3,  -0.090e-3,   0.081e-3,
       -0.324e-3,  -0.067e-3,  -0.761e-3,  -0.777e-3,   0.097e-3,
       -0.768e-3,  -0.706e-3,  -0.332e-3,  -0.298e-3,  -0.423e-3,
       -0.575e-3,  -0.700e-3,  -0.735e-3,  -0.744e-3,  -0.753e-3,
       -0.760e-3,  -0.765e-3,   0.009e-3,

        0.0,        0.0,        0.0,        0.0,        0.0,
        0.0,

        1.00,       0.82,       0.79,       0.85,       0.54,
        0.74,       0.61,       0.89,       0.55,       0.48,
        0.52,       0.50,       0.67,       0.65,       0.64,
        0.72,       0.43,       0.45,       1.00,       1.00,
        1.00,       0.68,       0.50,       1.00,       0.84,
        0.45,       0.84,       0.90,       0.95,       0.53,
        0.78,       0.80,       0.67,       0.90,       5.00 };



/* -------------- */
/* Prepare inputs */
/* -------------- */

/* Wavelength, and whether optical or radio. */
   w = ( wlfq != 0.0 ) ? wlfq : 0.1;
   if ( w < 0.0 ) {
      fq = - w;
      wl = c / fq;
   } else {
      wl = w;
      fq = c / wl;
   }
   wl = gmax ( wl, 0.1 );
   opt = ( wl <= 100.0 );

/* Transform supplied observed ZD into the normal (+/-pi) range. */
   zobs1 = slaDrange ( zobs );

/* Limit to a feasible value for ground-based applications. */
   w = fabs_ ( zobs1 );
   zobs2 = gmin ( w, opt ? zmaxo : zmaxr );

/* Keep other arguments within safe bounds. */
   w = gmax ( hm, -1000.0 );
   h0 = gmin ( w, hs );
   w = gmax ( tk, 100.0 );
   t0 = gmin ( w, 500.0 );
   w = gmax ( phpa, 0.0 );
   p0 = gmin ( w, 10000.0 );
   w  = gmax ( rh, 0.0 );
   rh0  = gmin ( w, 1.0 );
   w = fabs_ ( tlr );
   w = gmax ( w, 0.001 );
   alpha = gmin ( w, 0.01 );

/* Tolerance for iteration. */
   w = fabs_ ( eps );
   w = gmax ( w, 1e-12 );
   tol = gmin ( w, 0.1 ) / 2.0;

/* ------------------------------------- */
/* Water vapour pressure at the observer */
/* ------------------------------------- */

   tk2 = t0*t0;
   tk3 = tk2*t0;

/* Above or below triple point? */
   if ( t0 > 273.16 ) {

   /* Over water. */
      tk4 = tk2*tk2;
      e = - 2991.2729         / tk2
          - 6017.0128         / t0
          +   18.87643854
          -    0.028354721    * t0
          +    0.17838301e-4  * tk2
          -    0.84150417e-9  * tk3
          +    0.44412543e-12 * tk4
          +    2.858487       * log_(t0);
      w = t0 - 242.55 - 3.8e-2 * p0;
      w = 4.1e-4 + p0 * ( 3.48e-6 + 7.4e-10 * w * w );

   } else {

   /* Over ice. */
      e = - 5865.3696        / t0
          +   22.241033
          +    0.013749042   * t0
          -    0.34031775e-4 * tk2
          +    0.26967687e-7 * tk3
          +    0.6918651     * log_(t0);
      w = t0 - 249.35 - 3.1e-2 * p0;
      w = 4.8e-4 + p0 * ( 3.47e-6 + 5.9e-10 * w * w );
   }

/* Saturated water vapour pressure at the observer. */
   ps0 = ( w + 1.0 ) * exp_ ( e ) / 100.0;

/* Partial pressure of water vapour at the observer. */
   pw0 = ( p0 > 0.0 ) ?
         rh0 * ps0 / ( 1.0 - ( 1.0 - rh0 ) * ps0 / p0 ) :
         0.0;

/* ------------------------- */
/* Refractivity coefficients */
/* ------------------------- */

/* Optical or radio case? */
   if ( opt ) {

   /* ------- */
   /* Optical */
   /* ------- */

      w = wl*wl;
      a = ( ( 287.6155 + 1.62887/w + 0.01360 / ( w*w ) )
            * 273.15 / 1013.25 ) * 1e-6;
      bw = 11.2684e-6;
      cw = 0.0;

   } else {

   /* ----- */
   /* Radio */
   /* ----- */

   /* Partial pressure of dry air at the observer. */
      pd0 = p0 - pw0;

   /* Initialize complex dispersive refractivity. */
      znnx = znny = 0.0;

   /* Inverse temperature parameter. */
      th = 300.0 / t0;
      thsq = th * th;
      th1 = 1.0 - th;
      thp8 = pow_ ( th, 0.8 );

   /* O2 resonance lines. */
      q1 = pd0 * th * thsq;
      q2 = pd0 * thp8 + 1.1 * pw0 * th;
      q3 = p0 * thp8;
      for ( j = 0; j < 38; j++ ) {
         fj = fl[j];
         x1 = q1 * a1[j] * exp_ ( a2[j] * th1 ) / fj;
         y1 = - x1 * ( a5[j] + a6[j] * th ) * q3;
         w = a3[j] * q2;
         q = sqrt_ ( w * w + 2.25e-6 );
         qsq = q * q;
         x2 = fj - fq;
         w = x2*x2 + qsq;
         znnx += ( x1 * x2 - y1 * q ) / w;
         znny += ( y1 * x2 + x1 * q ) / w;
         x2 = fj + fq;
         w = x2 * x2 + qsq;
         znnx -= ( x1 * x2 - y1 * q ) / w;
         znny += ( y1 * x2 + x1 * q ) / w;
      }

   /* Nonresonant O2. */
      q2 = pd0 * pow_ ( th, 0.2 ) + 1.1 * pw0 * th;
      for ( j = 38; j < 44; j++ ) {
         fj = fl[j];
         x1 = q1 * a1[j] * exp_ ( a2[j] * th1 ) / fj;
         w = a3[j] * q2;
         q = sqrt_ ( w * w + 2.25e-6 );
         qsq = q * q;
         x2 = fj - fq;
         w = x1 / ( x2 * x2 + qsq );
         znnx += w * x2;
         znny += w * q;
         x2 = fj + fq;
         w = x1 / ( x2 * x2 + qsq );
         znnx -= w * x2;
         znny += w * q;
      }

      if ( znny < 0.0 ) znnx = 0.0;
      y2 = p0 * thp8 * 0.56e-3;
      znnx -= ( 6.14e-5 * pd0 * thsq ) * fq / ( fq * fq + y2 * y2 );

   /* H2O. */
      agd = 2.1316e-12 / th;
      q1 = pw0 * pow_ ( th, 3.5 );
      for ( j = 44; j < 79; j++ ) {
         fj = fl[j];
         x1 = q1 * a1[j] * exp_ ( a2[j] * th1 ) / fj;
         q = a3[j] * ( pd0 * pow_ ( th, a5[j] )
                     + pw0 * a4[j-44] * pow_ ( th, a6[j] ) );
         w = fj;
         q = 0.535 * q + sqrt_ ( 0.217 * q * q + agd * w * w );
         qsq = q * q;
         x2 = fj - fq;
         znnx += x1 * x2 / ( x2 * x2 + qsq );
         x2 = fj + fq;
         znnx -= x1 * x2 / ( x2 * x2 + qsq );
      }

   /* Refractivity coefficients. */
      a = ( 77.6890 + fq * znnx ) * 1e-6;
      bw = 6.3938e-6;
      cw = 375463e-6;
   }

/* ---------------------------------------------------- */
/* Prepare model atmosphere and refractivity quantities */
/* ---------------------------------------------------- */

   gb = 9.784 * ( 1.0 - 2.6e-3*cos_(2.0*phi) - 2.8e-7*h0 );
   gamal = gb * dmd / gcr;
   gamma = gamal / alpha;
   w = ( 1.0 - dmw / dmd ) * gamma / ( delta - gamma );
   f = pw0 / t0;
   q1 = a * ( p0 + w * pw0 ) / t0;
   q2 = ( a * w + bw ) * f;
   q2r = cw * f;
   q3 = alpha * ( gamma - 1.0 ) * q1 / t0;
   q4 = alpha * ( delta - 1.0 ) * q2 / t0;
   q4r = alpha * ( delta - 2.0 ) * q2r / ( t0 * t0 );

/* ---------------------------- */
/* Conditions at the boundaries */
/* ---------------------------- */

/* At the observer. */
   r0 = s + h0;
   atmt ( r0, t0, alpha, delta, gamma, q1, q2, q2r, q3, q4, q4r, r0,
          &t, &dn, &rdndr );
   sk0 = dn * r0 * sin_ ( zobs2 );
   f0 = refi ( dn, rdndr );

/* At the top of the troposphere. */
   rt = s + gmax ( ht, h0 );
   atmt ( r0, t0, alpha, delta, gamma, q1, q2, q2r, q3, q4, q4r, rt,
          &t, &dn, &rdndr );
   zt = asin_ ( sk0 / ( rt * dn ) );
   ft = refi ( dn, rdndr );
   q5 = dn - 1.0;
   q6 = gamal / t;

/* At the bottom of the stratosphere. */
   atms ( rt, q5, q6, rt, &dn, &rdndr );
   zts = asin_ ( sk0 / ( rt * dn ) );
   fts = refi ( dn, rdndr );

/* At the "top" of the stratosphere. */
   rs = s + hs;
   atms ( rt, q5, q6, rs, &dn, &rdndr );
   zs = asin_ ( sk0 / ( rs * dn ) );
   fs = refi ( dn, rdndr );

/* -------- */
/* Raytrace */
/* -------- */

/* Initialize the total refraction. */
   reft = 0.0;

/* Perform separate integrations for troposphere and stratosphere. */
   for ( layer = 1; layer <= 2; layer++ ) {

   /* Initialize previous refraction to ensure at least two iterations. */
      refold = 1.0;

   /* Start off with 8 strips. */
      is = 8;

   /* Integration parameters. */
      if ( layer == 1 ) {

   /* Troposphere. */
         z0 = zobs2;
         zrange = zt - z0;
         fb = f0;
         ff = ft;
         r1 = r0;

      } else {

   /* Stratosphere. */
         z0 = zts;
         zrange = zs - z0;
         fb = fts;
         ff = fs;
         r1 = rt;
      }

   /* Sums of odd and even values. */
      fo = fe = 0.0;

   /* First time through the loop we have to do every point. */
      n = 1;

   /* Start of iteration loop (terminates at specified precision). */
      for ( ; ; ) {

      /* Strip width */
         h = zrange / (double) is;

      /* Initialize distance from Earth centre for quadrature pass. */
         r = r1;

      /* One pass (no need to compute evens after first time). */
         for ( i = 1; i < is; i += n ) {

         /* Sine of observed zenith distance. */
            sz = sin_ ( z0 + h * (double) i );

         /* Find r for this ZD (nearest metre, max 4 iterations). */
            if ( sz > 1e-20 ) {
               w = sk0 / sz;
               j = 0;
               do {
                  if ( layer == 1 ) {
                     atmt ( r0, t0, alpha, delta, gamma,
                            q1, q2, q2r, q3, q4, q4r, r,
                            &t, &dn, &rdndr );
                  } else {
                     atms ( rt, q5, q6, r, &dn, &rdndr );
                  }
                  dr = ( r * dn - w ) / ( dn + rdndr );
                  r -= dr;
               } while ( fabs_ ( dr ) > 1.0 && j++ <= 4 );
            }

         /* Find refractive index and integrand at r. */
            if ( layer == 1 ) {
               atmt ( r0, t0, alpha, delta, gamma,
                      q1, q2, q2r, q3, q4, q4r, r,
                      &t, &dn, &rdndr );
            } else {
               atms ( rt, q5, q6, r, &dn, &rdndr );
            }
            f = refi ( dn, rdndr );

         /* Accumulate odd and (first time only) even values. */
            if ( n == 1 && i%2 == 0 ) {
               fe += f;
            } else {
               fo += f;
            }
         }

      /* Evaluate the integrand using Simpson's Rule. */
         refp = h * ( fb + 4.0 * fo + 2.0 * fe + ff ) / 3.0;

      /* Converged (or reached iteration limit)? */
         if ( fabs_ ( refp - refold ) <= tol || is >= ISMAX ) {

         /* Yes:  accumulate the refraction. */
            reft += refp;

         /* Proceed to next phase. */
            break;

         } else {

         /* Not yet: prepare for the next iteration. */
            refold = refp;   /* Remember latest estimate */
            is += is;        /* Double the number of strips */
            fe += fo;        /* Sum of all = sum of evens next time */
            fo = 0.0;        /* Reset odds accumulator */
            n = 2;           /* Skip even values next time */
         }
      }
   }

/* ------ */
/* Result */
/* ------ */

   *ref = ( zobs1 > 0.0 ) ? reft : -reft;
}

/*--------------------------------------------------------------------*/

static void atmt ( double r0, double t0, double alpha, double delta,
                   double gamma, double q1, double q2, double q2r,
                   double q3, double q4, double q4r, double r,
                   double *tr, double *dn, double *rdndr )
/*
**  - - - - -
**   a t m t
**  - - - - -
**
**  Internal function used by slaRefro:  in the troposphere, refractive
**  index and derivative with respect to height.
**
**  Given:
**    r0      double   height of observer from centre of the Earth (m)
**    t0      double   temperature at the observer (K)
**    alpha   double   tropospheric lapse rate (K/m)
**    delta   double   exponent of temperature dependence of Pw
**    gamma   double   exponent of temperature dependence of P
**    q1      double   miscellaneous term
**    q2r     double   miscellaneous term
**    q2      double   miscellaneous term (radio only)
**    q3      double   miscellaneous term
**    q4      double   miscellaneous term
**    q4r     double   miscellaneous term (radio only)
**    r       double   current distance from the centre of the Earth (m)
**
**  Returned:
**    *tr     double   temperature at r (K)
**    *dn     double   refractive index at r
**    *rdndr  double   r * rate the refractive index is changing at r
**
*/
{
   double t, w, wg, wd;


   t = t0 - alpha*(r-r0);
   w = t/t0;
   wg = pow_(w,gamma);
   wd = pow_(w,delta);
   *tr = t;
   *dn = 1.0 + ( q1*wg - ( q2 - q2r/t ) * wd ) / w;
   *rdndr = - r * ( q3*wg - q4*wd + q4r*wd/w ) / ( w*w );
}

/*--------------------------------------------------------------------*/

static void atms ( double rt, double q5, double q6, double r,
                   double *dn, double *rdndr )
/*
**  - - - - -
**   a t m s
**  - - - - -
**
**  Internal function used by slaRefro:  in the stratosphere, refractive
**  index and derivative with respect to height.
**
**  Given:
**    rt      double   geocentre to tropopause (m)
**    q5      double   miscellaneous term
**    q6      double   miscellaneous term
**    r       double   current distance from the centre of the Earth (m)
**
**  Returned:
**    *dn     double   refractive index at r
**    *rdndr  double   r * rate the refractive index is changing at r
**
*/
{
   double w;


   w = q5 * exp_ ( - q6 * ( r - rt ) );
   *dn = 1.0 + w;
   *rdndr = - r * q6 * w;
}

/*--------------------------------------------------------------------*/
