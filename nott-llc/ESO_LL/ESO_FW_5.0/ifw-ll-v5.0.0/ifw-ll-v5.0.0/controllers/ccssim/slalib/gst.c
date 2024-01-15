#include "TcPch.h"
#pragma hdrstop

#include "slalib.h"
#include "slamac.h"
double slaGst ( double date, double utdate, double ut )
/*
**  - - - - - - -
**   s l a G s t
**  - - - - - - -
**
**  Greenwich (apparent) sidereal time, from ERA and EO.
**
**  Given:
**    date    double    TDB Modified Julian Date
**    utdate  double    UT1 date (MJD: integer part of JD-2400000.5)
**    ut      double    UT1 time (fraction of a day)
**
**  Returned:
**            double    Greenwich apparent sidereal time (radians, in
**                      the range 0 to 2pi).
**
**  Notes:
**
**  1) The date is TDB as an MJD (=JD-2400000.5).  TT will do.
**
**  2) This Greenwich sidereal time is consistent with the latest and
**     most accurate of SLALIB's precession-nutation models.  It does
**     not use the conventional GMST formula and equation of the
**     equinoxes, but instead computes GST directly from the Earth
**     rotation angle and the equation of the origins (the distance
**     between the true equinox of date and the celestial intermediate
**     origin).
**
**  3) There is no restriction on how the UT is apportioned between the
**     utdate and ut arguments.  Either of the two arguments could, for
**     example, be zero and the entire date+time supplied in the other.
**     However, the function is designed to deliver maximum accuracy
**     when the utdate argument is a whole number and ut lies in the
**     range 0 to 1 (or vice versa).
**
**  Called:  slaDranrm, slaEra, slaEo
**
**  Last revision:   18 May 2009
**
**  Copyright P.T.Wallace.  All rights reserved.
*/
{

/* GAST = ERA - EO. */
   return slaDranrm ( slaEra ( utdate, ut ) - slaEo ( date ) );
}
