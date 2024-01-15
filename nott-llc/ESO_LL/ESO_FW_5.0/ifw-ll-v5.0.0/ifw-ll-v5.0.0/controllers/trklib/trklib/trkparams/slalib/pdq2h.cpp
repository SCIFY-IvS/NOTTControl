#include "../TcPch.h"
#pragma hdrstop

#include "slalib.h"
#include "slamac.h"
void slaPdq2h ( double p, double d, double q,
                double *h1, int *j1, double *h2, int *j2 )
/*
**  - - - - - - - - -
**   s l a P d q 2 h
**  - - - - - - - - -
**
**  Hour Angle corresponding to a given parallactic angle
**
**  (double precision)
**
**  Given:
**     p           double      latitude
**     d           double      declination
**     q           double      parallactic angle
**
**  Returned:
**     *h1         double      hour angle:  first solution if any
**     *j1         int         flag: 0 = solution 1 is valid
**     *h2         double      hour angle:  first solution if any
**     *j2         int         flag: 0 = solution 2 is valid
**
**  Called:  slaDrange
**
**  Defined in slamac.h:  DPI, DPIBY2
**
**  Last revision:   24 November 1994
**
**  Copyright P.T.Wallace.  All rights reserved.
*/

#define TINY 1e-12   /* Zone of avoidance around critical angles */

{
   double pn, qn, dn, sq, cq, sqsd, qt, qb, hpt, t;

/* Preset status flags to OK */
   *j1 = 0;
   *j2 = 0;

/* Adjust latitude, azimuth, parallactic angle to avoid critical values */
   pn = slaDrange ( p );
   if ( fabs_ ( fabs_ ( pn ) - DPIBY2 ) < TINY ) {
      pn -= dsign ( TINY, pn);
   } else if ( fabs_ ( pn ) < TINY ) {
      pn = TINY;
   }
   qn = slaDrange ( q );
   if ( fabs_ ( fabs_ ( qn ) - DPI ) < TINY ) {
      qn -= dsign ( TINY, qn );
   } else if ( fabs_ ( qn ) < TINY ) {
      qn = TINY;
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
   sq = sin_ ( qn );
   cq = cos_ ( qn );
   sqsd = sq * sin_ ( dn );

/* Quotient giving sin(h+t) */
   qt = sin_ ( pn ) * sq * cos_ ( dn );
   qb = cos_ ( pn ) * sqrt_ ( cq * cq + sqsd * sqsd );

/* Any solutions? */
   if ( fabs_ ( qt ) <= qb ) {

   /* Yes: find h+t and t */
      hpt = asin_ ( qt / qb );
      t = atan2_ ( sqsd, cq );

   /* The two solutions */
      *h1 = slaDrange ( hpt - t );
      *h2 = slaDrange ( - hpt - ( t + DPI ) );

   /* Reject if h and Q different signs */
      if ( *h1 * qn < 0.0 ) *j1 = - 1;
      if ( *h2 * qn < 0.0 ) *j2 = - 1;
   } else {
      *j1 = - 1;
      *j2 = - 1;
   }
}
