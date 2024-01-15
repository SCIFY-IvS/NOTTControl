#pragma once
#include "TcServices.h"

#include "trkmoduleServices.h"
#include "slalib/slalib.h"


void ComputeTracking(
	const SlaParams& params,
	const TrkMeanCoordinates& coord,
	ccsTIMEVAL& utc,
	TrackingData& trkdata);
