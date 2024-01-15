#include "TcPch.h"
#pragma hdrstop

#include "slalib.h"
#include "slamac.h"
void slaDav2m ( double axvec[3], double rmat[3][3] )
/*
**  - - - - - - - - -
**   s l a D a v 2 m
**  - - - - - - - - -
**
**  Form the rotation matrix corresponding to a given axial vector.
**
**  (double precision)
**
**  A rotation matrix describes a rotation about some arbitrary axis,
**  called the Euler axis.  The "axial vector" supplied to this function
**  has the same direction as the Euler axis, and its magnitude is the
**  amount of rotation in radians.
**
**  Given:
**    axvec  double[3]     axial vector (radians)
**
**  Returned:
**    rmat   double[3][3]  rotation matrix
**
**  If axvec is null, the unit matrix is returned.
**
**  The reference frame rotates clockwise as seen looking along
**  the axial vector from the origin.
**
**  Last revision:   22 October 2006
**
**  Copyright P.T.Wallace.  All rights reserved.
*/
{
  double x, y, z, phi, s, c, w;

/* Rotation angle - magnitude of axial vector - and functions */
   x   = axvec[0];
   y   = axvec[1];
   z   = axvec[2];
   phi = sqrt_ ( x * x + y * y + z * z );
   s   = sin_ ( phi );
   c   = cos_ ( phi );
   w   = 1.0 - c;

/* Euler axis - direction of axial vector (perhaps null) */
   if ( phi != 0.0 ) {
      x = x / phi;
      y = y / phi;
      z = z / phi;
   }

/* Compute the rotation matrix */
   rmat[0][0] = x * x * w + c;
   rmat[0][1] = x * y * w + z * s;
   rmat[0][2] = x * z * w - y * s;
   rmat[1][0] = x * y * w - z * s;
   rmat[1][1] = y * y * w + c;
   rmat[1][2] = y * z * w + x * s;
   rmat[2][0] = x * z * w + y * s;
   rmat[2][1] = y * z * w - x * s;
   rmat[2][2] = z * z * w + c;
}
