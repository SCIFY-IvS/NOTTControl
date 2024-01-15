#include "TcPch.h"
#pragma hdrstop

#include "slalib.h"
#include "slamac.h"
void slaTp2s ( float xi, float eta, float raz, float decz,
               float *ra, float *dec )
/*
**  - - - - - - - -
**   s l a T p 2 s
**  - - - - - - - -
**
**  Transform tangent plane coordinates into spherical.
**
**  (single precision)
**
**  Given:
**     xi,eta      float  tangent plane rectangular coordinates
**     raz,decz    float  spherical coordinates of tangent point
**
**  Returned:
**     *ra,*dec    float  spherical coordinates (0-2pi,+/-pi/2)
**
**  Called:        slaRanorm
**
**  Last revision:   10 July 1994
**
**  Copyright P.T.Wallace.  All rights reserved.
*/
{
   float sdecz, cdecz, denom, radif;

   sdecz = (float) sin_ ( decz );
   cdecz = (float) cos_ ( decz );

   denom = cdecz - eta * sdecz;
   radif = (float) atan2_ ( xi, denom );

   *ra = slaRanorm ( radif + raz );
   *dec = (float) atan2_ ( sdecz + eta * cdecz ,
                          sqrt_ ( xi * xi + denom * denom ) );
}
