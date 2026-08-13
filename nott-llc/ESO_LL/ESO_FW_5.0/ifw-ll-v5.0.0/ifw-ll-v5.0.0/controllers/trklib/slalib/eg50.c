#include "TcPch.h"
#pragma hdrstop

#include "slalib.h"
#include "slamac.h"
void slaEg50 ( double dr, double dd, double *dl, double *db )
/*
**  - - - - - - - -
**   s l a E g 5 0
**  - - - - - - - -
**
**  Transformation from B1950.0 'FK4' equatorial coordinates to
**  IAU 1958 galactic coordinates.
**
**  (double precision)
**
**  Given:
**     dr,dd       double       B1950.0 'FK4' RA,dec
**
**  Returned:
**     *dl,*db     double       galactic longitude and latitude l2,b2
**
**  (all arguments are radians)
**
**  Called:
**     slaDcs2c, slaDmxv, slaDcc2s, slaSubet, slaDranrm, slaDrange
**
**  Note:
**     The equatorial coordinates are B1950.0 'FK4'.  Use the
**     function slaEqgal if conversion from J2000.0 coordinates
**     is required.
**
**  Reference:
**     Blaauw et al., 1960, Mon.Not.R.astron.Soc., 121, 123
**
**  Last revision:   23 July 2007
**
**  Copyright P.T.Wallace.  All rights reserved.
*/
{
   double v1[3], v2[3], r, d;

/*
** l2,b2 system of galactic coordinates
**
** p = 192.25       RA of galactic north pole (mean B1950.0)
** q =  62.6        inclination of galactic to mean B1950.0 equator
** r =  33          longitude of ascending node
**
** p,q,r are degrees
**
** Equatorial to galactic rotation matrix
**
** The Euler angles are p, q, 90-r, about the z then y then
** z axes.
**
**        +cp.cq.sr-sp.cr     +sp.cq.sr+cp.cr     -sq.sr
**
**        -cp.cq.cr-sp.sr     -sp.cq.cr+cp.sr     +sq.cr
**
**        +cp.sq              +sp.sq              +cq
*/

   static double rmat[3][3] =
   {
      { -0.066988739415151, -0.872755765851993, -0.483538914632184 },
      {  0.492728466075324, -0.450346958019961,  0.744584633283031 },
      { -0.867600811151435, -0.188374601722920,  0.460199784783852 }
   };


/* Remove e-terms. */
   slaSubet ( dr, dd, 1950.0, &r, &d );

/* Spherical to Cartesian. */
   slaDcs2c ( r, d, v1 );

/* Rotate to Galactic. */
   slaDmxv ( rmat, v1, v2 );

/* Cartesian to spherical. */
   slaDcc2s ( v2, dl, db );

/* Express angles in conventional ranges. */
   *dl = slaDranrm ( *dl );
   *db = slaDrange ( *db );
}
