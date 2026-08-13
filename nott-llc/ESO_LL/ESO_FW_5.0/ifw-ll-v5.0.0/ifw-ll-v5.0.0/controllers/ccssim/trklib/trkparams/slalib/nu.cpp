#include "../TcPch.h"
#pragma hdrstop

#include "slalib.h"
#include "slamac.h"
void slaNu ( double date, double *dpsi, double *deps )
/*
**  - - - - - -
**   s l a N u
**  - - - - - -
**
**  Nutation, IAU 2006 model (IAU 2000A nutation with corrections
**  applied to match the IAU 2006 precession).
**
**  Given:
**     date        double   TDB Modified Julian Date
**
**  Returned:
**     dpsi,deps   double*  nutation, luni-solar + planetary
**
**  Called:  slaNu00a
**
**  Notes:
**
**  1) The date is TDB as an MJD (=JD-2400000.5).  TT will do.
**
**  2) The nutation components in longitude and obliquity are with
**     respect to the mean equinox and ecliptic of date, IAU 2006
**     precession model (Hilton et al. 2006, Capitaine et al. 2005).
**
**  3) The function first computes the IAU 2000A nutation then applies
**     corrections for (i) the consequences of the change in obliquity
**     from the IAU 1980 ecliptic to the IAU 2006 ecliptic and (ii) the
**     secular variation in the Earth's dynamical flattening, not taken
**     into account in the IAU 2000A model.
**
**  4) The present function provides classical nutation, supplementing
**     the IAU 2000 frame bias and IAU 2006 precession.  It delivers a
**     pole which is at current epochs accurate to a few tens of
**     microarcseconds, apart from the omission of the free core
**     nutation.
**
**  References:
**
**     Capitaine, N., Wallace, P.T. & Chapront, J. 2005,
**     Astron.Astrophys. 432, 355-357
**
**     Hilton, J. et al., 2006, Celest.Mech.Dyn.Astron. 94, 351
**
**  Last revision:   22 October 2006
**
**  Copyright P.T.Wallace.  All rights reserved.
*/

#define DJC 36525.0            /* Days per Julian century */
#define DJM0 51544.5           /* Reference epoch (J2000), MJD */

{
   double t, fj2, dp, de;



/* Interval between fundamental epoch J2000.0 and current date (JC). */
   t = ( date - DJM0 ) / DJC;

/* Factor correcting for secular variation of J2. */
   fj2 = - 2.7774e-6 * t;

/* Obtain IAU 2000A nutation. */
   slaNu00a ( date, &dp, &de );

/* Apply P03 corrections (Capitaine et al. 2005, expr. 29-30). */
   *dpsi = dp + dp * ( 0.4697e-6 + fj2 );
   *deps = de + de * fj2;

}
