#include "../TcPch.h"
#pragma hdrstop

#include "slalib.h"
#include "slamac.h"
void slaDtp2s ( double xi, double eta, double raz, double decz,
                double *ra, double *dec )
/*
**  - - - - - - - - -
**   s l a D t p 2 s
**  - - - - - - - - -
**
**  Transform tangent plane coordinates into spherical.
**
**  (double precision)
**
**  Given:
**     xi,eta      double   tangent plane rectangular coordinates
**     raz,decz    double   spherical coordinates of tangent point
**
**  Returned:
**     *ra,*dec    double   spherical coordinates (0-2pi,+/-pi/2)
**
**  Called:  slaDranrm
**
**  Last revision:   3 June 1995
**
**  Copyright P.T.Wallace.  All rights reserved.
*/
{
  double sdecz, cdecz, denom;

  sdecz = sin_ ( decz );
  cdecz = cos_ ( decz );
  denom = cdecz - eta * sdecz;
  *ra = slaDranrm ( atan2_ ( xi, denom ) + raz );
  *dec = atan2_ ( sdecz + eta * cdecz, sqrt_ ( xi * xi + denom * denom ) );
}
