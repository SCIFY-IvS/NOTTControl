#include "TcPch.h"
#pragma hdrstop

#include "slalib.h"
#include "slamac.h"
void slaI2cqk ( double ri, double di, CIpars *ciprms,
                double *rc, double *dc )
/*
**  - - - - - - - - -
**   s l a I 2 c q k
**  - - - - - - - - -
**
**  Quick CIRS RA,Dec to ICRS astrometric place, given the star-
**  independent parameters.
**
**  Use of this function is appropriate when efficiency is important and
**  where many star positions are all to be transformed for one date.
**  The star-independent parameters can be obtained by calling the
**  slaC2ipa function.
**
**  Given:
**     ri,di     double    CIRS RA,Dec (radians)
**     ciprms    CIpars*   star-independent ICRS-to-CIRS parameters:
**      pmt        double    time interval for proper motion (Jyears)
**      eb[3]      double    SSB to Earth (AU)
**      ehn[3]     double    Sun to Earth unit vector
**      gr2e       double    (grav rad Sun)*2/(Sun-Earth distance)
**      abv[3]     double    barycentric Earth velocity in units of c
**      ab1        double    sqrt(1-v**2) where v=modulus(abv)
**      bpn[3][3]  double    bias-precession-nutation matrix
**
**  Returned:
**     rc,dc     double*   ICRS astrometric RA,Dec (radians)
**
**  Note:
**
**     Iterative techniques are used for the aberration and light
**     deflection corrections so that the functions slaI2c (or slaI2cqk)
**     and slaC2i (or slaC2iqk) are accurate inverses;  even at the edge
**     of the Sun's disc the discrepancy is only about 1 nanoarcsecond.
**
**  Reference:
**     Explanatory Supplement to the Astronomical Ephemeris, Chapter 3.
**
**  Called:  slaDcs2c, slaDimxv, slaDvdv, slaDvn, slaDcc2s, slaDranrm
**
**  This revision:   17 January 2006
**
**  Copyright P.T.Wallace.  All rights reserved.
*/
{
   int i, j;
   double gr2e, ab1, ehn[3], abv[3], p3[3], p2[3],
          ab1p1, p1dv, p1dvp1, p1[3], w, pde, pdep1, p[3];



/* Unpack scalar and vector parameters. */
   gr2e = ciprms->gr2e;
   ab1 = ciprms->ab1;
   for ( i = 0; i < 3; i++ ) {
      ehn[i] = ciprms->ehn[i];
      abv[i] = ciprms->abv[i];
   }

/* CIRS RA,Dec to Cartesian. */
   slaDcs2c ( ri, di, p3 );

/* Bias-precession-nutation. */
   slaDimxv ( ciprms->bpn, p3, p2 );

/* Aberration. */
   ab1p1 = ab1 + 1.0;
   for ( i = 0; i < 3; i++ ) {
      p1[i] = p2[i];
   }
   for ( j = 0; j < 2; j++ ) {
      p1dv = slaDvdv ( p1, abv );
      p1dvp1 = 1.0 + p1dv;
      w = 1.0 + p1dv / ab1p1;
      for ( i = 0; i < 3; i++ ) {
         p1[i] = ( p1dvp1*p2[i] - w*abv[i] ) / ab1;
      }
      slaDvn ( p1, p3, &w );
      for ( i = 0; i < 3; i++ ) {
         p1[i] = p3[i];
      }
   }

/* Light deflection. */
   for ( i = 0; i < 3; i++ ) {
      p[i] = p1[i];
   }
   for ( j = 0; j < 5; j++ ) {
      pde = slaDvdv ( p, ehn );
      pdep1 = 1.0 + pde;
      w = pdep1 - gr2e*pde;
      for ( i = 0; i < 3; i++ ) {
         p[i] = ( pdep1*p1[i] - gr2e*ehn[i] ) / w;
      }
      slaDvn ( p, p2, &w );
      for ( i = 0; i < 3; i++ ) {
         p[i] = p2[i];
      }
   }

/* ICRS astrometric RA,Dec. */
   slaDcc2s ( p, rc, dc );
   *rc = slaDranrm ( *rc );

}
