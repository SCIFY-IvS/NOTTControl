#include "TcPch.h"
#pragma hdrstop

#include "slalib/slalib.h"
#include "TimeFunctions.h"

/*
 *****************************************************************************
 * timeUTCToJD: convert struct ccsTIMEVAL into Julian date
 *
 *  IN   ut: time in UT
 *  OUT    : Julian date
 *****************************************************************************
 */
DOUBLE timeUTCToJD(ccsTIMEVAL *ut)    /* time in UT                       */
{
	DOUBLE jd;

	/*
	 * CONST4 = jd(70-01-01 00:00:00.000000)
	 */
	jd = CONST4 + (ut->tv_sec + ut->tv_usec / 1000000.) / 86400.;
	return(jd);
}

/*
 *****************************************************************************
 * timeUTCToMJD: convert struct ccsTIMEVAL into modified Julian date
 *
 *  IN   ut: time in UT
 *  OUT    : Modified julian date
 *****************************************************************************
 */
DOUBLE timeUTCToMJD(ccsTIMEVAL *ut)   /* time in UT                       */
{
	DOUBLE mjd;                       /* modified julian date             */
   /*
	*# Get Julian Date from UT
	*/
	mjd = timeUTCToJD(ut);

	/*
	 *# Convert Julian Date into Modified Julian Date according to the formula:
	 *# MJD = JD - 2400000.5;
	 */
	mjd -= CONST3;
	return(mjd);
}

/*
 *****************************************************************************
 * timeGetUTC: Get UTC time from TwinCAT DC time
 *
 *  IN   dcTime: TwinCAT DC time
 *  OUT  eltUTC: UTC time
 *****************************************************************************
 */
HRESULT timeGetUTC(LONGLONG dcTime, ccsTIMEVAL *ccsUTC)
{
	HRESULT hr = S_OK;

	// DC time is in nano seconds
	ccsUTC->tv_sec = (LONGLONG)(dcTime / 1000000000);
	ccsUTC->tv_usec = (dcTime - (ccsUTC->tv_sec * 1000000000)) / 1000;

	// Added offset between year 1970 and 2000 needed by the different references
	// used in UNIX and TWINCAT
	ccsUTC->tv_sec += OFFSET_UNIX;
	return hr;
}

/*
 *****************************************************************************
 * timeGetUTCInFuture: Get UTC time from TwinCAT DC time but ahead of time
 *
 *  IN   dcTime: TwinCAT DC time
 *  IN   time_ahead: Time in the future in usecs
 *  OUT  eltUTC: UTC time
 *****************************************************************************
 */
HRESULT timeGetUTCInFuture(LONGLONG dcTime, ccsTIMEVAL *ccsUTC, LONGLONG time_ahead)
{
	HRESULT hr = S_OK;

	// DC time is in nano seconds
	ccsUTC->tv_sec = (LONGLONG)(dcTime / 1000000000);
	ccsUTC->tv_usec = (dcTime - (ccsUTC->tv_sec * 1000000000)) / 1000;

	// Added offset between year 1970 and 2000 needed by the different references
	// used in UNIX and TWINCAT
	ccsUTC->tv_sec += OFFSET_UNIX;
	ccsUTC->tv_usec += time_ahead;
	return hr;
}

/*
 *****************************************************************************
 * timeGetDcTime: Get TwinCAT DC time from UTC time
 *
 *  IN   eltUTC: UTC time
 *  OUT  dcTIME: TwinCAT DC time
 *****************************************************************************
 */
HRESULT timeGetDcTime(ccsTIMEVAL ccsUTC, LONGLONG *dcTime)
{
	HRESULT hr = S_OK;
	LONGLONG val = 0;
	val = ccsUTC.tv_sec * 1000000000;
	val -= OFFSET_UNIX;
	*dcTime = val + ccsUTC.tv_usec * 1000;
	return hr;
}


/*
 *****************************************************************************
 * timeGetAbsoluteDcTime: Adjust DC time based on the external time signal
 *
 *  IN   ptptime    : UTC time difference with respect local time
 *  OUT  dcTIME     : Adjusted TwinCAT DC time
 *****************************************************************************
 */
 
 HRESULT timeGetAbsoluteDcTime(LONGLONG timeDiff, LONGLONG *dcTime)
 {
	 HRESULT hr = S_OK;
	
	 *dcTime -= timeDiff;
	 return hr;
 }
 

 /*
 void timeMJDToDateTime(DOUBLE mjd)
 {
	 // convert mjd into years/months/days/fractionOfDays
	 int years, months, days, status;
	 double fod;
	 slaDjcl(mjd, &years, &months, &days, &fod, &status);



	 // convert fractionOfDays into hours/minutes/microseconds
	 int ihmsf[4];
	 int decimalPlacesOfMicroseconds = 6;
	 char sign;
	 slaDd2tf(decimalPlacesOfMicroseconds, fod, &sign, ihmsf);



 } */
