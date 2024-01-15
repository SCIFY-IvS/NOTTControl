#include "../TcPch.h"
#pragma hdrstop

#include "slalib.h"
#include "slamac.h"
void slaPda2h ( double p, double d, double a,
                double *h1, int *j1, double *h2, int *j2 )
/*
**  - - - - - - - - -
**   s l a P d a 2 h
**  - - - - - - - - -
**
**  Hour Angle corresponding to a given azimuth
**
**  (double precision)
**
**  Given:
**     p           double      latitude
**     d           double      declination
**     a           double      azimuth
**
**  Returned:
**     *h1         double      hour angle:  first solution if any
**     *j1         int         flag: 0 = solution 1 is valid
**     *h2         double      hour angle:  first solution if any
**     *j2         int         flag: 0 = solution 2 is valid
**
**  Defined in slamac.h:  DPI, DPIBY2
**
**  Last revision:   24 November 1994
**
**  Copyright P.T.Wallace.  All rights reserved.
*/

#define TINY 1e-12   /* Zone of avoidance around critical angles */

{
   double pn, an, dn, sa, ca, sasp, qt, qb, hpt, t;

/* Preset status flags to OK */
   *j1 = 0;
   *j2 = 0;

/* Adjust latitude, azimuth, declination to avoid critical values */
   pn = slaDrange ( p );
   if ( fabs_ ( fabs_ ( pn ) - DPIBY2 ) < TINY ) {
      pn -= dsign ( TINY, pn);
   } else if ( fabs_ ( pn ) < TINY ) {
      pn = TINY;
   }
   an = slaDrange ( a );
   if ( fabs_ ( fabs_ ( an ) - DPI ) < TINY ) {
      an -= dsign ( TINY, an );
   } else if ( fabs_ ( an ) < TINY ) {
      an = TINY;
   }
   dn = slaDrange ( d );
   if ( fabs_ ( fabs_ ( dn ) - fabs_ ( p ) ) < TINY ) {
      dn -= dsign ( TINY, dn );
   } else if ( fabs_ ( fabs_ ( dn ) - DPIBY2 ) < TINY ) {
      dn -= dsign ( TINY, dn );
   } else if ( fabs_ ( dn ) < TINY ) {
      dn = TINY;
   }

/* Useful functions */
   sa = sin_ ( an );
   ca = cos_ ( an );
   sasp = sa * sin_ ( pn );

/* Quotient giving sin(h+t) */
   qt = sin_ ( dn ) * sa * cos_ ( pn );
   qb = cos_ ( dn ) * sqrt_ ( ca * ca + sasp * sasp );

/* Any solutions? */
   if ( fabs_ ( qt ) <= qb ) {

   /* Yes: find h+t and t */
      hpt = asin_ ( qt / qb );
      t = atan2_ ( sasp, - ca );

   /* The two solutions */
      *h1 = slaDrange ( hpt - t );
      *h2 = slaDrange ( - hpt - ( t + DPI ) );

   /* Reject unless h and A different signs */
      if ( *h1 * an > 0.0 ) *j1 = - 1;
      if ( *h2 * an > 0.0 ) *j2 = - 1;
   } else {
      *j1 = - 1;
      *j2 = - 1;
   }
}
