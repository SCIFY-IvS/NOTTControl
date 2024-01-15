#include "TcPch.h"
#pragma hdrstop

#include "slalib/slalib.h"
#include "astro.h"

/*
 *   tcsSplitHms   :   Split an angle,given in user format, to its
 *   ===========      parts.
 *
 *   Given    :  angle      an angle as hhmmss.ttt (or ddmmss.tt)
 *   Returned :  h          hours (degrees)
 *               m          minutes (arcminutes)
 *               s          seconds (arcseconds)
 *
 *    The given time/angle, a floating value in the format HHMMSS.TTT, is split
 *    up in the parts HH, MM and SS.TTT (or DDMMSS.TTT if the input parameter
 *    is an angle).
 *          NOTE:   if the given value is negative, all returned values
 *    will also be negative! Which is may be not what you want, so take care of
 *    the sign outside of this function!
 *
 *
 *   EXAMPLES
 *    Example 1:
 *     double time,h,m,s;
 *     time=123456.7;
 *     i=astroSplitHms(time,&h,&m,&s);
 *
 *        will return  h=12.0
 *                     m=34.0
 *                     s=56.7
 *
 *
 *   Example 2:
 *     double time,h,m,s;
 *     time=345.0;
 *     i=astroSpltHms(time,&h,&m,&s);
 *
 *        will return  h=0.0
 *                     m=3.0
 *                     s=45.0
 *
 */
void astroSplitHms(double angle, double *h, double *m, double *s)
{
	double val;
	double hour, min, sec, t1, t2, t3;

	val = angle;
	sec = val - (int)(val / 100.0)*100.0;
	t1 = val - sec;
	t2 = t1 - (int)(t1 / 10000.0)*10000.0;
	min = t2 / 100.0;
	t3 = val - sec - t2;
	hour = t3 / 10000;
	*h = hour;
	*m = min;
	*s = sec;
	return;
}

/*
 *   astroHms2rad   :   Convert a time/angle,given in user format, to radians.
 *   ===========
 *
 *   Given    :  angle      an angle as hhmmss.ttt (HoursMinutesSecs)
 *   Returned :  rad        the angle as radians
 *
 *    The given time/angle, a floating value in the format HHMMSS.TTT, is
 *    converted to radians. See also tcsSplitHms
 */
double astroHms2rad(double angle)
{
	double hh, hm, hs;
	double rad, rar;
	double de2ra = 0.017453292519943;

	astroSplitHms(fabs_(angle), &hh, &hm, &hs);
	rad = (hh + hm / 60.0 + hs / 3600.0)*15.0;
	rar = rad * de2ra;
	if (angle < 0.0) rar = -rar;

	return(rar);
}

/*
 *   astroDms2rad   :   Convert an angle,given in user format, to radians.
 *   ===========
 *
 *   Given    :  angle      an angle as ddmmss.ttt (DegreesMinutesSecs)
 *   Returned :  rad        the angle as radians
 *
 *    The given angle, a floating value in the format DDMMSS.TTT, is
 *    converted to radians. See also tcsSplitHms.
 */
double astroDms2rad(double angle)
{
	double hh, hm, hs;
	double ded, der;
	double de2ra = 0.017453292519943;

	astroSplitHms(fabs_(angle), &hh, &hm, &hs);
	ded = hh + hm / 60.0 + hs / 3600.0;
	if (angle < 0.0) ded = -ded;
	der = ded * de2ra;

	return(der);
}

/*
 *   astroRad2Hms   : Convert a time/angle,given in radians, to 'user format'
 *   ===========      hhmmss.ttt
 *
 *   Given    :  rad        the angle as radians
 *   Returned :  angle      an angle as hhmmss.ttt (HoursMinutesSecs)
 *
 *     See also tcsHms2Rad (which is the opposite function!)
 */
double astroRad2Hms(double angle)
{
	/*
   double hh,hm,hs;
   double temp;
   */
	double hms;
	int ihmsf[4];
	char sign[2];

	slaDr2tf(6, angle, sign, ihmsf);
	hms = (ihmsf[0] * 10000.0 + ihmsf[1] * 100.0 + ihmsf[2] + ihmsf[3] / 1000000.0) * (*sign == '-' ? -1 : 1);

	return(hms);
}

/*
 *   astroRad2Dms   : Convert an angle,given in radians, to 'user format'
 *   ===========      ddmmss.ttt
 *
 *   Given    :  rad        the angle as radians
 *   Returned :  angle      an angle as ddmmss.ttt
 *
 *     See also tcsDms2Rad (which is the opposite function!)
 *
 */
double astroRad2Dms(double angle)
{
	/*
   double hh,hm,hs;
   double temp,hms;
   */
	double hms;
	int idmsf[4];
	char sign[2];


	slaDr2af(6, angle, sign, idmsf);
	hms = (idmsf[0] * 10000.0 + idmsf[1] * 100.0 + idmsf[2] + idmsf[3] / 1000000.0) * (*sign == '-' ? -1 : 1);

	return(hms);
}

