#include "../TcPch.h"
#pragma hdrstop

#include "slalib.h"
#include "slamac.h"
void slaPomom ( double date, double xp, double yp, double rpom[3][3] )
/*
**  - - - - - - - - -
**   s l a P o m o m
**  - - - - - - - - -
**
**  Form the matrix of polar motion for a given date.
**
**  Given:
**     date     double        TDB Modified Julian Date (Note 1)
**     xp,yp    double        coordinates of the pole (radians, Note 2)
**
**  Returned:
**     rpom     double[3][3]  polar-motion matrix (Note 4)
**
**  Notes:
**
**  1) The date is TDB as an MJD (=JD-2400000.5).  The result is
**     extremely insensitive to the date, so TT or even UTC can be
**     used.
**
**  2) xp and yp are the "coordinates of the pole", in radians, which
**     position the Celestial Intermediate Pole in the International
**     Terrestrial Reference System (see IERS Conventions 2003).  In a
**     geocentric right-handed triad u,v,w, where the w-axis points at
**     the north geographic pole, the v-axis points towards the origin
**     of longitudes and the u-axis completes the system, xp = +u and
**     yp = -v.
**
**  3) The other angle needed is the quantity s', which positions the
**     terrestrial intermediate origin on the equator.  A standard model
**     is used.
**
**  4) The matrix operates in the sense v(TRS) = rpom * v(CIP), meaning
**     that it is the final rotation when computing the pointing
**     direction to a celestial source.
**
**  Called:  slaSp, slaDeuler
**
**  Reference:
**
**     McCarthy, D. D., Petit, G. (eds.) 2004, IERS Conventions (2003),
**     IERS Technical Note No. 32, BKG
**
**  Last revision:   8 January 2006
**
**  Copyright P.T.Wallace.  All rights reserved.
*/
{

/* Construct the matrix. */
   slaDeuler ( "zyx", slaSp ( date ), -xp, -yp, rpom );

}
