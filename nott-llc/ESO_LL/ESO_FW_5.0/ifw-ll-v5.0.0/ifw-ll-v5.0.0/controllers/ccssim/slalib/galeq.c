#include "TcPch.h"
#pragma hdrstop

#include "slalib.h"
#include "slamac.h"
void slaGaleq ( double dl, double db, double *dr, double *dd )
/*
**  - - - - - - - - -
**   s l a G a l e q
**  - - - - - - - - -
**
**  Transformation from IAU 1958 galactic coordinates to
**  J2000.0 equatorial coordinates.
**
**  (double precision)
**
**  Given:
**     dl,db       double      galactic longitude and latitude l2,b2
**
**  Returned:
**     *dr,*dd     double      J2000.0 RA,dec
**
**  (all arguments are radians)
**
**  Called:
**     slaDcs2c, slaDimxv, slaDcc2s, slaDranrm, slaDrange
**
**  Note:
**     The equatorial coordinates are J2000.0.  Use the function
**     slaGe50 if conversion to B1950.0 'FK4' coordinates is
**     required.
**
**  Reference:
**     Blaauw et al., 1960, Mon.Not.R.astron.Soc., 121, 123
**
**  Last revision:   23 July 2007
**
**  Copyright P.T.Wallace.  All rights reserved.
*/
{
   double v1[3], v2[3];

/*
**  l2,b2 system of Galactic coordinates
**
**  p = 192.25       RA of galactic north pole (mean B1950.0)
**  q =  62.6        inclination of galactic to mean B1950.0 equator
**  r =  33          longitude of ascending node
**
**  p,q,r are degrees
**
**  Equatorial to galactic rotation matrix (J2000.0), obtained by
**  applying the standard FK4 to FK5 transformation, for zero proper
**  motion in FK5, to the rows of the B1950 equatorial to galactic
**  rotation matrix with E-terms added:
*/
   static double rmat[3][3] =
   {
      { -0.054875539695716, -0.873437107995315, -0.483834985836994 },
      {  0.494109453305607, -0.444829589431879,  0.746982251810510 },
      { -0.867666135847849, -0.198076386130820,  0.455983795721093 }
   };


/* Spherical to Cartesian. */
   slaDcs2c ( dl, db, v1 );

/* Galactic to equatorial. */
   slaDimxv ( rmat, v1, v2 );

/* Cartesian to spherical. */
   slaDcc2s ( v2, dr, dd );

/* Express in conventional ranges. */
   *dr = slaDranrm ( *dr );
   *dd = slaDrange ( *dd );
}
