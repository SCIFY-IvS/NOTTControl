#include "TcPch.h"
#pragma hdrstop

#include "slalib.h"
#include "slamac.h"
double slaSp ( double date )
/*
**  - - - - - -
**   s l a S p
**  - - - - - -
**
**  The quantity s', positioning the terrestrial intermediate origin on
**  the equator of the intermediate pole.
**
**  Given:
**     date      double   date, TDB Modified Julian Date (Note 1)
**
**  Returned:
**     slaSp00   double   the quantity s' in radians (Note 2)
**
**  Notes:
**
**  1) The date is TDB as an MJD (=JD-2400000.5).  TT (or even UTC) will
**     do.
**
**  2) The quantity s' is obtained from polar motion observations by
**     numerical integration, and so is in essence unpredictable.
**     However, it is dominated by a secular drift of about
**     47 microarcseconds per century, which is the approximation
**     evaluated by the present function.
**
**  Defined in slamac.h:  DAS2R
**
**  Reference:
**
**     McCarthy, D.D., Petit, G. (eds.) 2004, IERS Conventions (2003),
**     IERS Technical Note No. 32, BKG
**
**  Last revision:   22 October 2006
**
**  Copyright P.T.Wallace.  All rights reserved.
*/

#define DJC 36525.0            /* Days per Julian century */
#define DJM0 51544.5           /* Reference epoch (J2000), MJD */

{
   double t;


/* Interval between fundamental epoch J2000.0 and current date (JC). */
   t = ( date - DJM0 ) / DJC;

/* Approximate s'. */
   return - 47e-6 * t * DAS2R;

}
