#include "../TcPch.h"
#pragma hdrstop

#include "slalib.h"
#include "slamac.h"
void slaFw2m  ( double gamb, double phib, double psi, double eps,
                double r[3][3] )
/*
**  - - - - - - - -
**   s l a F w 2 m
**  - - - - - - - -
**
**  Form rotation matrix given the Fukushima-Williams angles.
**
**  Given:
**     gamb     double        F-W angle gamma_bar (radians)
**     phib     double        F-W angle phi_bar (radians)
**     psi      double        F-W angle psi (radians)
**     eps      double        F-W angle epsilon (radians)
**
**  Returned:
**     r        double[3][3]  rotation matrix
**
**  Notes:
**
**  1) Naming the following points:
**
**           e = J2000 ecliptic pole,
**           p = GCRS pole,
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
**        NxPxB = R_1(-eps).R_3(-psi).R_1(phib).R_3(gamb)
**
**  3) Three different matrices can be constructed, depending on the
**     supplied angles:
**
**     . To obtain the nutation x precession x frame bias matrix,
**       generate the four precession angles, generate the nutation
**       components and add them to the psi_bar and epsilon_A angles,
**       and call the present function.
**
**     . To obtain the precession x frame bias matrix, generate the four
**       precession angles and call the present function.
**
**     . To obtain the frame bias matrix, generate the four precession
**       angles for date J2000.0 and call the present function.
**
**     The nutation-only and precession-only matrices can if necessary
**     be obtained by combining these three appropriately.
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
   double sgam, cgam, sphi, cphi, spsi, cpsi, seps, ceps;


/* Functions of Fukushima-Williams angles. */
   sgam = sin_(gamb);
   cgam = cos_(gamb);
   sphi = sin_(phib);
   cphi = cos_(phib);
   spsi = sin_(psi);
   cpsi = cos_(psi);
   seps = sin_(eps);
   ceps = cos_(eps);

/* Matrix elements. */
   r[0][0] = cpsi*cgam + spsi*cphi*sgam;
   r[0][1] = cpsi*sgam - spsi*cphi*cgam;
   r[0][2] = - spsi*sphi;
   r[1][0] = ceps*spsi*cgam - (ceps*cpsi*cphi+seps*sphi)*sgam;
   r[1][1] = ceps*spsi*sgam + (ceps*cpsi*cphi+seps*sphi)*cgam;
   r[1][2] = ceps*cpsi*sphi - seps*cphi;
   r[2][0] = seps*spsi*cgam - (seps*cpsi*cphi-ceps*sphi)*sgam;
   r[2][1] = seps*spsi*sgam + (seps*cpsi*cphi-ceps*sphi)*cgam;
   r[2][2] = seps * cpsi*sphi + ceps*cphi;

}
