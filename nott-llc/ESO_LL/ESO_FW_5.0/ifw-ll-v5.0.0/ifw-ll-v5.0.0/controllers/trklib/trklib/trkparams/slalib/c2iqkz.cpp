#include "../TcPch.h"
#pragma hdrstop

#include "slalib.h"
#include "slamac.h"
void slaC2iqkz  ( double rc, double dc, CIpars *ciprms,
                  double *ri, double *di )
/*
**  - - - - - - - - - -
**   s l a C 2 i q k z
**  - - - - - - - - - -
**
**  Quick ICRS RA,Dec, epoch J2000, to CIRS, given the star-independent
**  parameters, and assuming zero parallax and proper motion.
**
**  Use of this function is appropriate when efficiency is important and
**  where many star positions, all with parallax and proper motion either
**  zero or already allowed for, are to be transformed for one date.  The
**  star-independent parameters can be obtained by calling the slaC2ipa
**  function.
**
**  The corresponding function for the case of non-zero parallax and
**  proper motion is slaC2iqk.
**
**  Given:
**     rc,dc  double    ICRS RA,Dec at J2000 (radians)
**     ciprms CIpars*   star-independent ICRS-to-CIRS parameters:
**      pmt        double    time interval for proper motion (Jyears)
**      eb[3]      double    SSB to Earth (AU)
**      ehn[3]     double    Sun to Earth unit vector
**      gr2e       double    (grav rad Sun)*2/(Sun-Earth distance)
**      abv[3]     double    barycentric Earth velocity in units of c
**      ab1        double    sqrt(1-v**2) where v=modulus(abv)
**      bpn[3][3]  double    bias-precession-nutation matrix
**
**  Returned:
**     ri,di  double*   CIRS RA,Dec (radians)
**
**  Notes:
**
**  1)  The vectors ciprms->eb and ciprms->ehn are in the BCRS.
**
**  2)  Strictly speaking, the function is not valid for solar-system
**      sources, though the error will usually be extremely small.
**      However, to prevent gross errors in the case where the
**      position of the Sun is specified, the gravitational
**      deflection term is restrained within about 920 arcsec of the
**      center of the Sun's disc.  The term has a maximum value of
**      about 1.85 arcsec at this radius, and decreases to zero as
**      the centre of the disc is approached.
**
**  Called:  slaDcs2c, slaDvdv, slaDmxv, slaDcc2s, slaDranrm
**
**  Last revision:   19 January 2006
**
**  Copyright P.T.Wallace.  All rights reserved.
*/
{
   int i;

   double p[3], pde, pdep1, w, p1[3], p1dv, p2[3], p3[3];



/* Spherical to x,y,z. */
   slaDcs2c ( rc, dc, p );

/* Light deflection (restrained within the Sun's disc). */
   pde = slaDvdv ( p, ciprms->ehn );
   pdep1 = pde + 1.0;
   w = ciprms->gr2e / gmax ( pdep1, 1.0e-5 );
   for ( i = 0; i < 3; i++ ) {
      p1[i] = p[i] + w * ( ciprms->ehn[i] - pde * p[i] );
   }

/* Aberration (normalization omitted). */
   p1dv = slaDvdv ( p1, ciprms->abv );
   w = 1.0 + p1dv / ( ciprms->ab1 + 1.0 );
   for ( i = 0; i < 3; i++ ) {
      p2[i] = ciprms->ab1 * p1[i] + w * ciprms->abv[i];
   }

/* Bias-precession-nutation. */
   slaDmxv ( ciprms->bpn, p2, p3 );

/* CIRS RA,Dec. */
   slaDcc2s ( p3, ri, di );
   *ri = slaDranrm ( *ri );

}
