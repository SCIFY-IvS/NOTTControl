#include "TcPch.h"
#pragma hdrstop

#include "slalib.h"
#include "slamac.h"
void slaPncio ( double date, double rnpb[3][3] )
/*
**  - - - - - - - - -
**   s l a P n c i o
**  - - - - - - - - -
**
**  Form the CIO based precession-nutation matrix, with respect to the
**  geocentric celestial reference system.
**
**  Given:
**     date   double        TDB Modified Julian Date
**
**  Returned:
**     rnpb   double[3][3]  combined nutation x precession x bias matrix
**
**  Called:  slaPfw, slaNu, slaFw2xy, slaG2ixys, slaS
**
**  Notes:
**
**  1) The date is TDB as an MJD (=JD-2400000.5).  TT will do.
**
**  2)  The matrix is in the sense   V(CIRS) = RNPB * V(GCRS)
**
**  Last revision:   3 January 2006
**
**  Copyright P.T.Wallace.  All rights reserved.
*/
{
   double gamb, phib, psib, epsa, dp, de, x, y;


/* Frame bias + precession angles. */
   slaPfw ( date, &gamb, &phib, &psib, &epsa );

/* Nutation components. */
   slaNu ( date, &dp, &de );

/* CIP X,Y. */
   slaFw2xy ( gamb, phib, psib + dp, epsa + de, &x, &y );

/* CIO based NPB matrix. */
   slaG2ixys ( x, y, slaS ( date, x, y ), rnpb );

}
