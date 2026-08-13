#include "TcPch.h"
#pragma hdrstop

#include "slalib.h"
#include "slamac.h"
void slaPfw ( double date,
              double *gamb, double *phib, double *psib, double *epsa )
/*
**  - - - - - - -
**   s l a P f w
**  - - - - - - -
**
**  Precession angles, IAU 2006 (Fukushima-Williams 4-angle
**  formulation).
**
**  Given:
**     date     double    TDB Modified Julian Date
**
**  Returned:
**     gamb     double*   F-W angle gamma_bar (radians)
**     phib     double*   F-W angle phi_bar (radians)
**     psib     double*   F-W angle psi_bar (radians)
**     epsa     double*   F-W angle epsilon_A (radians)
**
**  Notes:
**
**  1) The date is TDB as an MJD (=JD-2400000.5).  TT will do.
**
**  2) Naming the following points:
**
**           e = J2000 ecliptic pole,
**           p = GCRS pole,
**           E = mean ecliptic pole of date,
**     and   P = mean pole of date,
**
**     the four Fukushima-Williams angles are as follows:
**
**        gamb = gamma_bar = epE
**        phib = phi_bar = pE
**        psib = psi_bar = pEP
**        epsa = epsilon_A = EP
**
**  3) The matrix representing the combined effects of frame bias and
**     precession is:
**
**        PxB = R_1(-epsa).R_3(-psib).R_1(phib).R_3(gamb)
**
**  4) The matrix representing the combined effects of frame bias,
**     precession and nutation is simply:
**
**        NxPxB = R_1(-epsa-dE).R_3(-psib-dP).R_1(phib).R_3(gamb)
**
**     where dP and dE are the nutation components with respect to the
**     ecliptic of date.
**
**  Reference:
**
**     Hilton, J. et al., 2006, Celest.Mech.Dyn.Astron. 94, 351
**
**  Defined in slamac.h:  DAS2R
**
**  Last revision:   22 October 2006
**
**  Copyright P.T.Wallace.  All rights reserved.
*/

#define DJC 36525.0            /* Days per Julian century */
#define DJM0 51544.5           /* Reference epoch (J2000), MJD */

{
   double t;



/* Interval between fundamental epoch J2000.0 and current date (JC). */
   t = ( date - DJM0 ) / DJC;

/* P03 bias+precession angles. */

   *gamb = (   - 0.052928       +
           (    10.556378       +
           (     0.4932044      +
           (   - 0.00031238     +
           (   - 0.000002788    +
           (     0.0000000260 ) * t ) * t ) * t ) * t ) * t ) * DAS2R;

   *phib = ( 84381.412819       +
           (  - 46.811016       +
           (     0.0511268      +
           (     0.00053289     +
           (   - 0.000000440    +
           (   - 0.0000000176 ) * t ) * t ) * t ) * t ) * t ) * DAS2R;

   *psib = (   - 0.041775       +
           (  5038.481484       +
           (     1.5584175      +
           (   - 0.00018522     +
           (   - 0.000026452    +
           (   - 0.0000000148 ) * t ) * t ) * t ) * t ) * t ) * DAS2R;

   *epsa = ( 84381.406          +
           (  - 46.836769       +
           (   - 0.0001831      +
           (     0.00200340     +
           (   - 0.000000576    +
           (   - 0.0000000434 ) * t ) * t ) * t ) * t ) * t ) * DAS2R;

}
