#include "TcPch.h"
#pragma hdrstop

#include "slalib.h"
#include "slamac.h"
double slaEra ( double date, double ut )
/*
**  - - - - - - -
**   s l a E r a
**  - - - - - - -
**
**  Earth rotation angle (IAU 2000 expression).
**
**  Given:
**    date   double    UT1 date (MJD: integer part of JD-2400000.5)
**    ut     double    UT1 time (fraction of a day)
**
**  The result is the Earth rotation angle (radians), in the range 0 to
**  2pi.
**
**  Notes:
**
**  1)  There is, in fact, no restriction on how the UT is apportioned
**      between the date and ut arguments.  Either of the two arguments
**      could, for example, be zero and the entire date+time supplied in
**      the other.  However, the function is designed to deliver maximum
**      accuracy when the date argument is a whole number and the ut
**      argument lies in the range 0 to 1, or vice versa.
**
**  2)  The algorithm is adapted from Expression 22 of Capitaine et al.
**      2000.  The time argument has been expressed in days directly,
**      and, to retain precision, integer contributions have been
**      eliminated at the earliest opportunity.
**
**  Defined in slamac.h:  D2PI
**
**  Called:  slaDranrm
**
**  Reference:
**     Capitaine N., Guinot B. and McCarthy D.D, 2000, A&A 355,
**     398-405.
**
**  Last revision:  22 October 2006
**
**  Copyright P.T.Wallace.  All rights reserved.
*/

#define DJM0 51544.5  /* Reference epoch (J2000), MJD */

{
   double d1, d2, t, f;


/* Days since fundamental epoch. */
   if ( date < ut ) {
      d1 = date;
      d2 = ut;
   } else {
      d1 = ut;
      d2 = date;
   }
   t = d1 + ( d2 - DJM0 );

/* Fractional part of UT days (perhaps plus a small integer). */
   f = fmod_ ( d1, 1.0 ) + fmod_ ( d2, 1.0 ) + 0.5;

/* Earth rotation angle at this UT1. */
   return slaDranrm  ( D2PI *
             ( f + 0.7790572732640 + 0.00273781191135448 * t ) );

}
