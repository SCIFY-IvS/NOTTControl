#include "TcPch.h"
#pragma hdrstop

#include "slalib.h"
#include "slamac.h"
void slaPneqx ( double date, double rnpb[3][3] )
/*
**  - - - - - - - - -
**   s l a P n e q x
**  - - - - - - - - -
**
**  Form the classical precession-nutation matrix, with respect to the
**  geocentric celestial reference system.
**
**  Given:
**     date   double        TDB Modified Julian Date
**
**  Returned:
**     rnpb   double[3][3]  combined nutation x precession x bias matrix
**
**  Called:  slaPfw, slaNu, slaFw2m
**
**  Notes:
**
**  1) The date is TDB as an MJD (=JD-2400000.5).  TT will do.
**
**  2)  The matrix is in the sense   V(true) = RNPB * V(GCRS)
**
**  Last revision:   30 December 2005
**
**  Copyright P.T.Wallace.  All rights reserved.
*/
{
   double gamb, phib, psib, epsa, dp, de;


/* Frame bias + precession angles. */
   slaPfw ( date, &gamb, &phib, &psib, &epsa );

/* Nutation components. */
   slaNu ( date, &dp, &de );

/* Equinox based nutation x precession x bias matrix. */
   slaFw2m ( gamb, phib, psib + dp, epsa + de, rnpb );

}
