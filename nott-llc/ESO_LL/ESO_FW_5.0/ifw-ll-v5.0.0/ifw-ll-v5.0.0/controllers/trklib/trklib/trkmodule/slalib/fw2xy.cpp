#include "../TcPch.h"
#pragma hdrstop

#include "slalib.h"
#include "slamac.h"
void slaFw2xy ( double gamb, double phib, double psi, double eps,
                double *x, double *y )
/*
**  - - - - - - - - -
**   s l a F w 2 x y
**  - - - - - - - - -
**
**  CIP X,Y given Fukushima-Williams bias-precession-nutation angles.
**
**  Given:
**     gamb     double    F-W angle gamma_bar (radians)
**     phib     double    F-W angle phi_bar (radians)
**     psi      double    F-W angle psi (radians)
**     eps      double    F-W angle epsilon (radians)
**
**  Returned:
**     x,y      double*   CIP X,Y ("radians")
**
**  Notes:
**
**  1) Naming the following points:
**
**           e = J2000 ecliptic pole,
**           p = GCRS pole
**           E = ecliptic pole of date,
**     and   P = CIP,
**
**     the four Fukushima-Williams angles are as follows:
**
**        gamb = gamma = epE
**        phib = phi = pE
**        psi = psi = pEP
**        eps = epsilon = EP
**
**  2) The matrix representing the combined effects of frame bias,
**     precession and nutation is:
**
**        NxPxB = R_1(-epsa).R_3(-psi).R_1(phib).R_3(gamb)
**
**     X,Y are elements (3,1) and (3,2) of the matrix.
**
**  Reference:
**
**     Hilton, J. et al., 2006, Celest.Mech.Dyn.Astron. 94, 351
**
**  Last revision:   22 October 2006
**
**  Copyright P.T.Wallace.  All rights reserved.
*/
{
   double sg, cg, sp, se, cpcp, cesp;


/* X,Y components of pole unit vector. */
   sg = sin_(gamb);
   cg = cos_(gamb);
   sp = sin_(psi);
   se = sin_(eps);
   cpcp = cos_(psi) * cos_(phib);
   cesp = cos_(eps) * sin_(phib);
   *x = se * ( sp*cg - cpcp*sg ) + cesp*sg;
   *y = se * ( sp*sg + cpcp*cg ) - cesp*cg;

}
