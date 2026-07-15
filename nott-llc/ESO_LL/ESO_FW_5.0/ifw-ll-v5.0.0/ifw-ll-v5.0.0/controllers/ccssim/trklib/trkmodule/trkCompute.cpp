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
	PointingKernelPositions& trkdata) {
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
	
	double ra = apparent_r.alpha;
	double dec = apparent_r.delta;
	trkdata.radec_at_altaz_at_requested_xy[0] = apparent_r.alpha;
	trkdata.radec_at_altaz_at_requested_xy[1] = apparent_r.delta;
	
	// Compute observed coordinates
	TrkObservedCoordinates observed_r;
	slaAopqk(apparent_r.alpha, apparent_r.delta, aoprms,
		&observed_r.az, &observed_r.zd, &observed_r.ha, &observed_r.delta, &observed_r.alpha);

	// Compute tracking values
	trkdata.time_lst = lst;
	
	
	double alt = DPIBY2 - observed_r.zd;
	double az = -(observed_r.az + DPI);

	if (az < 0.0) {
		az += D2PI;
	}

	trkdata.parallactic_angle = slaPa(observed_r.ha, observed_r.delta, phi);
	
	trkdata.target_observed_altaz[0] = alt;
	trkdata.target_observed_altaz[1] = az;
	trkdata.current_observed_altaz[0] = trkdata.target_observed_altaz[0];
	trkdata.current_observed_altaz[1] = trkdata.target_observed_altaz[1];

	trkdata.north_angle = trkdata.parallactic_angle + alt;
	trkdata.pupil_angle = alt;

}

