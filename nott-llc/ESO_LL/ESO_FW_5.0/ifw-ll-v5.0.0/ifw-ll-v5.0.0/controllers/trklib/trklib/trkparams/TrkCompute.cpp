#include "TcPch.h"
#pragma hdrstop



#include "TimeFunctions.h"
#include "TrkCompute.h"


void ComputeTracking(
	const CcsData& ccsdata,
	ccsTIMEVAL& utc,
	SlaParams& params) {

	double mjd;

	mjd = timeUTCToMJD(&utc);
	
	// precompute apparent-to-observed parameters
	double amprms[21] = { 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0 };
	slaMappa(ccsdata.equinox, mjd, amprms);

	memcpy(&params.mappa, &amprms, sizeof(params.mappa));

	double aoprms[14] = { 0,0,0,0,0,0,0,0,0,0,0,0,0,0 };

	slaAoppa(mjd,
		ccsdata.dut,
		ccsdata.site.longitude * (-1.0),
		ccsdata.site.latitude,
		ccsdata.site.height,
		ccsdata.motion.x,
		ccsdata.motion.y,
		ccsdata.environment.temperature + 273.15,   /* temperaure in K */
		ccsdata.environment.pressure,
		ccsdata.environment.humidity * 0.01,        /* rel. humidity as fraction, i.e between 0 and 1 */
		ccsdata.wavelength * 0.001,                 /* wavelength in micrometer */
		ccsdata.environment.lapserate,
		aoprms);

	memcpy(&params.aoppa, &aoprms, sizeof(params.aoppa));
}
