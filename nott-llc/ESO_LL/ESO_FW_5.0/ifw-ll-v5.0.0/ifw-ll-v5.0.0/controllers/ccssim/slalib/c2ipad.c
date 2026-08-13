#include "TcPch.h"
#pragma hdrstop

#include "slalib.h"
#include "slamac.h"
void slaC2ipad ( CIpars *ciprms )
/*
**  - - - - - - - - - -
**   s l a C 2 i p a d
**  - - - - - - - - - -
**
**  In the ICRS to CIRS star-independent parameters, disable bias-
**  precession-nutation.  Subsequent calls to slaC2iqk will consequently
**  produce GCRS coordinates rather than CIRS.
**
**  Given:
**     ciprms CIpars*   star-independent ICRS-to-CIRS parameters
**      pmt        double    time interval for proper motion (Jyears)
**      eb[3]      double    SSB to Earth (AU)
**      ehn[3]     double    Sun to Earth unit vector
**      gr2e       double    (grav rad Sun)*2/(Sun-Earth distance)
**      abv[3]     double    barycentric Earth velocity in units of c
**      ab1        double    sqrt(1-v**2) where v=modulus(abv)
**      bpn[3][3]  double    bias-precession-nutation matrix
**
**  Returned:
**     ciprms CIpars*   star-independent ICRS-to-GCRS parameters:
**      pmt        double    unchanged
**      eb[3]      double    unchanged
**      ehn[3]     double    unchanged
**      gr2e       double    unchanged
**      abv[3]     double    unchanged
**      ab1        double    unchanged
**      bpn[3][3]  double    identity matrix
**
**  Last revision:   17 January 2006
**
**  Copyright P.T.Wallace.  All rights reserved.
*/
{
   int i, j;


/* Replace the NxPxB matrix with the identity matrix. */
   for ( i = 0; i < 3; i++ ) {
      for ( j = 0; j < 3; j++ ) {
         ciprms->bpn[i][j] = ( i == j ? 1.0 : 0.0 );
      }
   }
}
