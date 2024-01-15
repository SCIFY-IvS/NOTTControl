#include "../TcPch.h"
#pragma hdrstop

#include "slalib.h"
#include "slamac.h"
double slaEo ( double date )
/*
**  - - - - - -
**   s l a E o
**  - - - - - -
**
**  Equation of the origins.
**
**  Given:
**     date    double     TDB Modified Julian Date
**
**  Returned:
**             double     the equation of the origins (radians)
**
**  Called:  slaPneqx, slaEors, slaS
**
**  Notes:
**
**  1)  The date is TDB as an MJD (=JD-2400000.5).  TT will do.
**
**  2)  The equation of the origins is the distance between the true
**      equinox and the celestial intermediate origin and, equivalently,
**      the difference between Earth rotation angle and Greenwich
**      apparent sidereal time (ERA-GST).  It comprises the precession
**      (since J2000.0) in right ascension plus the equation of the
**      equinoxes (including the small correction terms).
**
**  3)  To transform a geocentric apparent right ascension into the
**      equivalent right ascension in the celestial intermediate
**      reference system (CIRS), add the equation of the origins.
**
**  Reference:
**
**     Capitaine, N. & Wallace, P.T. 2006, A&A (submitted).
**
**  Last revision:   24 February 2008
**
**  Copyright P.T.Wallace.  All rights reserved.
*/
{
   double r[3][3];


/* Classical nutation x precession x bias matrix. */
   slaPneqx ( date, r );

/* Using that matrix and the quantity s, solve for the EO. */
   return slaEors ( r, slaS ( date, r[2][0], r[2][1] ) );

}
