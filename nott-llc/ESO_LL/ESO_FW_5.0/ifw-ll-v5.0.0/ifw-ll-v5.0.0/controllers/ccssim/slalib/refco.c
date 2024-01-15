#include "TcPch.h"
#pragma hdrstop

#include "slalib.h"
#include "slamac.h"
void slaRefco ( double hm, double tk, double phpa, double rh,
                double wlfq, double phi, double tlr, double eps,
                double *refa, double *refb )
/*
**  - - - - - - - - -
**   s l a R e f c o
**  - - - - - - - - -
**
**  Determine constants A and B in atmospheric refraction model
**  dz = A tan z + B tan^3 z.
**
**  z is the "observed" zenith distance (i.e. affected by
**  refraction) and dz is what to add to z to give the "topocentric"
**  (i.e. in vacuo) zenith distance.
**
**  Given:
**    hm    double    height of the observer above sea level (metre)
**    tk    double    ambient temperature at the observer (K)
**    phpa  double    pressure at the observer (hPa = millibar)
**    rh    double    relative humidity at the observer (range 0-1)
**    wlfq  double    wavelength (micron) or minus frequency (GHz)
**    phi   double    latitude of the observer (radian, astronomical)
**    tlr   double    temperature lapse rate in the troposphere (K/metre)
**    eps   double    precision required to terminate iteration (radian)
**
**  Returned:
**    *refa double    tan z coefficient (radian)
**    *refb double    tan^3 z coefficient (radian)
**
**  Called:  slaRefro
**
**  Notes:
**
**  1  Typical values for the tlr and eps arguments might be 0.0065 and
**     1e-10 respectively.
**
**  2  The argument wlfq specifies whether optical or radio and the
**     wavelength/frequency.  Positive values specify wavelength in
**     microns and are the usual way of selecting the optical case.
**     Negative values specify frequency in GHz and are the usual way of
**     selecting the radio case.  The transition from optical to radio
**     is assumed to occur at 100 microns (about 3000 GHz).
**
**  3  The function is a slower but more accurate alternative to the
**     slaRefcoq function.  The constants it produces give perfect
**     agreement with slaRefro at zenith distances arctan(1) (45 deg)
**     and arctan(4) (about 76 deg).  It achieves 0.5 arcsec accuracy
**     for ZD < 80 deg, 0.01 arcsec accuracy for ZD < 60 deg, and
**     0.001 arcsec accuracy for ZD < 45 deg.
**
**  Last revision:   11 August 2008
**
**  Copyright P.T.Wallace.  All rights reserved.
*/
{
   double r1,r2;

/* Sample zenith distances: arctan(1) and arctan(4) */
   static double atn1 = 0.7853981633974483;
   static double atn4 = 1.325817663668033;

/* Determine refraction for the two sample zenith distances. */
   slaRefro ( atn1, hm, tk, phpa, rh, wlfq, phi, tlr, eps, &r1 );
   slaRefro ( atn4, hm, tk, phpa, rh, wlfq, phi, tlr, eps, &r2 );

/* Solve for refraction constants. */
   *refa = ( 64.0 * r1 - r2 ) / 60.0;
   *refb = ( r2 - 4.0 * r1 ) / 60.0;
}
