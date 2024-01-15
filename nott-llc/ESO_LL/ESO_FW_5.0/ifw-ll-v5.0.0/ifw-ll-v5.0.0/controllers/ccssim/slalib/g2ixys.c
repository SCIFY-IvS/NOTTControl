#include "TcPch.h"
#pragma hdrstop

#include "slalib.h"
#include "slamac.h"
void slaG2ixys ( double x, double y, double s, double rc2i[3][3] )
/*
**  - - - - - - - - - -
**   s l a G 2 i x y s
**  - - - - - - - - - -
**
**  Form the GCRS to CIRS matrix given the CIP X,Y and the CIO locator
**  s.
**
**  Given:
**     x,y    double        celestial intermediate pole (Note 1)
**     s      double        the quantity s (Note 2)
**
**  Returned:
**     rc2i   double[3][3]  GCRS-to-CIRS matrix (Note 3)
**
**  Notes:
**
**  1) The celestial intermediate pole coordinates are the x,y
**     components of the unit vector in the GCRS.
**
**  2) The quantity s (in radians) positions the celestial intermediate
**     origin on the equator of the CIP.
**
**  3) The matrix rc2i is the first stage in the transformation from
**     celestial to terrestrial coordinates:
**
**        [TRS]  =  RPOM * R_3(ERA) * RC2I * [CRS]
**
**     where [CRS] is a vector in the Geocentric Celestial Reference
**     System and [TRS] is a vector in the International Terrestrial
**     Reference System, ERA is the Earth rotation angle and RPOM is the
**     polar motion matrix.
**
**  Called:  slaDeuler
**
**  Reference:
**
**     McCarthy, D.D., Petit, G. (eds.) 2004, IERS Conventions (2003),
**     IERS Technical Note No. 32, BKG
**
**  Last revision:   7 January 2006
**
**  Copyright P.T.Wallace.  All rights reserved.
*/
{
   double r2, e, d;


/* Obtain the spherical angles E and d. */
   r2 = x*x + y*y;
   e = r2 != 0.0 ? atan2_ ( y, x ) : 0.0;
   d = atan_ ( sqrt_ ( r2 / ( 1.0 - r2 ) ) );

/* Form the matrix. */
   slaDeuler ( "zyz", e, d, - ( e + s ), rc2i );

}
