#include "TcPch.h"
#pragma hdrstop

#include "Astro.h"
#include "slalib/slamac.h"
#include "TimeFunctions.h"



#include "Computation.h"

void ComputeTracking(
	const SlaParams& params,
	const TrkMeanCoordinates& mean,
	ccsTIMEVAL& utc,
	TrackingData& trkdata) {
	double mjd;
	
	mjd = timeUTCToMJD(&utc);

	TrkMeanCoordinates mean_r;

	mean_r.alpha = astroHms2rad(mean.alpha);
	mean_r.delta = astroDms2rad(mean.delta);
	mean_r.pma = mean.pma * (DAS2R / cos_(mean_r.delta));
	mean_r.pmd = mean.pmd * DAS2R;

	double amprms[21] = { 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0 };
	double aoprms[14] = { 0,0,0,0,0,0,0,0,0,0,0,0,0,0 };

	memcpy(&amprms, &params.mappa, sizeof(amprms));
	memcpy(&aoprms, &params.aoppa, sizeof(aoprms));
	
	// recompute sideral time in aoprms[13]
	slaAoppat(mjd, aoprms);

	double lst = aoprms[13]; /* sidereal time */
	double phi = aoprms[0];  /* latitude */

	// Compute apparent coordinates
	//slaMapqkz(mean_r.alpha, mean_r.delta, amprms, &(apparent.alpha), &(apparent.delta));
	
	TrkApparentCoordinates apparent_r;
	slaMapqk(mean_r.alpha, mean_r.delta,
		mean_r.pma, mean_r.pmd,
		mean.parallax,
		mean.radvel,
		amprms, &(apparent_r.alpha), &(apparent_r.delta));
	
	trkdata.computation.ra = apparent_r.alpha;
	trkdata.computation.dec = apparent_r.delta;
	trkdata.apparent.alpha = astroRad2Hms(apparent_r.alpha);
	trkdata.apparent.delta = astroRad2Dms(apparent_r.delta);
	

	// Compute observed coordinates

	TrkObservedCoordinates observed_r;
	slaAopqk(apparent_r.alpha, apparent_r.delta, aoprms,
		&observed_r.az, &observed_r.zd, &observed_r.ha, &observed_r.delta, &observed_r.alpha);

	trkdata.observed.alpha = astroRad2Hms(observed_r.alpha);
	trkdata.observed.delta = astroRad2Dms(observed_r.delta);

	// Compute tracking values
	trkdata.computation.lst = lst;
	
	trkdata.computation.alt = DPIBY2 - observed_r.zd;
	trkdata.computation.alt_deg = trkdata.computation.alt * DR2D;
	trkdata.computation.az = -(observed_r.az + DPI);
	if (trkdata.computation.az < 0.0) {
		trkdata.computation.az += D2PI;
	}
	trkdata.computation.az = dmod(trkdata.computation.az, D2PI);
	trkdata.computation.az_deg = trkdata.computation.az * DR2D;
	trkdata.computation.ha = observed_r.ha;

	trkdata.computation.pa = slaPa(observed_r.ha, observed_r.delta, phi);
	trkdata.computation.pa_deg = trkdata.computation.pa * DR2D;
	



}

