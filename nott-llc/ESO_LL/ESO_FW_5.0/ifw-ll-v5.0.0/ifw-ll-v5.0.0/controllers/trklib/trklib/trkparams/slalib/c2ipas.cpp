#include "../TcPch.h"
#pragma hdrstop

#include "slalib.h"
#include "slamac.h"
void slaC2ipas ( double date, double pv[2][3], double dx, double dy,
                 CIpars *ciprms, double *eo )
/*
**  - - - - - - - - - -
**   s l a C 2 i p a s
**  - - - - - - - - - -
**
**  For an observer not necessarily coincident with the geocenter,
**  compute star-independent parameters in preparation for
**  transformations between ICRS star data and CIRS RA,Dec.
**
**  The parameters produced by this function are required in the
**  parallax, light deflection, aberration and precession-nutation parts
**  of the ICRS/CIRS transformations.
**
**  Given:
**     date    double       TDB (JD-2400000.5)
**     pv      double[2][3] observer's geocentric position and velocity
**     dx      double       CIP X-correction (radians)
**     dy      double       CIP Y-correction (radians)
**
**  Returned:
**     ciprms  CIpars*      star-independent ICRS-to-CIRS parameters:
**      pmt        double    time interval for proper motion (Jyears)
**      eb[3]      double    SSB to Earth (AU)
**      ehn[3]     double    Sun to Earth unit vector
**      gr2e       double    (grav rad Sun)*2/(Sun-Earth distance)
**      abv[3]     double    observer's barycentric velocity / c
**      ab1        double    sqrt(1-v**2) where v=modulus(abv)
**      bpn[3][3]  double    bias-precession-nutation matrix
**     eo      double*      equation of the origins (ERA-GST)
**
**  Notes:
**
**  1)  For date, the distinction between the required TDB and TT is
**      always negligible.  Moreover, for all but the most critical
**      applications UTC is adequate.
**
**  2)  The vectors ciprms->eb and ciprms->ehn are in the BCRS.
**
**  3)  The parameters ciprms produced by this function are used by
**      slaC2iqk, slaC2iqkz and slaI2cqk.  The bias-precession-
**      nutation portion can be suppressed using slaC2ipad, allowing
**      transformations to and from GCRS instead of CIRS.
**
**  4)  The accuracy is sub-milliarcsecond, limited by the precession-
**      nutation information (IAU 2006 model plus the CIP corrections,
**      which are obtained from IERS bulletins).
**
**  5)  The accuracy is in principle further limited by the function
**      slaEpv00, called by slaC2ipa, which computes the Earth position
**      and velocity.  The maximum error arising from this source is
**      less than 5 microarcseconds.
**
**  6)  The observer's position and velocity pv are in GCRS coordinates
**      and in units of km and km/s.
**
**  Called:  slaEpj, slaEpv, slaDvn, slaPfw, slaNu, slaFw2m, slaG2ixys,
**           slaS
**
**  Last revision:   15 August 2007
**
**  Copyright P.T.Wallace.  All rights reserved.
*/

#define AUKM ( 149.597870691e6 )     /* AU to km */
#define AUDKMS ( AUKM / 86400.0 )    /* AU/d to km/s */
#define CR ( 499.004782 / 86400.0 )  /* Light time for 1 AU (day) */
#define GR2 ( 2.0 * 9.87063e-9 )     /* Gravitational radius of the
                                        Sun x 2 (2*mu/c**2, AU) */
{
   int i;

   double ph[3], vh[3], pb[3], vb[3], dp, dv, e, vn[3], vm,
          gam, phi, psi, eps, dpsi, deps, r[3][3], x, y, s;



/* Time interval for proper motion correction. */
   ciprms->pmt = slaEpj ( date ) - 2000.0;

/* Earth barycentric and heliocentric position (AU) and velocity (AU/d). */
   slaEpv ( date, ph, vh, pb, vb );

/* Refer to the observer. */
   for ( i = 0; i < 3; i++ ) {
      dp = pv[0][i] / AUKM;
      dv = pv[1][i] / AUDKMS;
      pb[i] += dp;
      vb[i] += dv;
      ph[i] += dp;
   }

/* Barycentric position (AU). */
   for ( i = 0; i < 3; i++ ) {
      ciprms->eb[i] = pb[i];
   }

/* Heliocentric distance and position (unit vector). */
   slaDvn ( ph, ciprms->ehn, &e );

/* Light deflection parameter */
   ciprms->gr2e = GR2 / e;

/* Barycentric velocity in units of c, and other aberration quantity. */
   for ( i = 0; i < 3; i++ ) {
      ciprms->abv[i] = vb[i] * CR;
   }
   slaDvn ( ciprms->abv, vn, &vm  );
   ciprms->ab1 = sqrt_ ( 1.0 - vm * vm );

/* Frame bias+precession+nutation angles. */
   slaPfw ( date, &gam, &phi, &psi, &eps );
   slaNu ( date, &dpsi, &deps );
   psi += dpsi;
   eps += deps;

/* Equinox based NPB matrix (prior to CIP corrections). */
   slaFw2m ( gam, phi, psi, eps, r );

/* Extract (uncorrected) CIP X,Y. */
   x = r[2][0];
   y = r[2][1];

/* CIO locator s (CIP corrections do not apply). */
   s = slaS ( date, x, y );

/* Equation of the origins. */
   *eo = slaEors ( r, s );

/* Form the CIO based NPB matrix (including CIP corrections). */
   slaG2ixys ( x+dx, y+dy, s, ciprms->bpn );

}
