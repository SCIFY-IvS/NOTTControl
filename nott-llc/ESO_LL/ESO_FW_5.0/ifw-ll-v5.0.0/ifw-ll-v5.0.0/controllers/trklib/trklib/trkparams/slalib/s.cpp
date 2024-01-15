#include "../TcPch.h"
#pragma hdrstop

#include "slalib.h"
#include "slamac.h"
double slaS ( double date, double x, double y )
/*
**  - - - - -
**   s l a S
**  - - - - -
**
**  The quantity s, positioning the celestial intermediate origin on the
**  equator of the celestial intermediate pole, given the CIP's X,Y
**  coordinates.
**
**  Given:
**     date   double    TDB Modified Julian Date (Note 1)
**     x,y    double    CIP coordinates (Note 3)
**
**  Returned:
**            double    the quantity s, in radians (Note 2)
**
**  Notes:
**
**  1) The date is TDB as an MJD (=JD-2400000.5).  TT (or even UTC) will
**     do.
**
**  2) The CIO locator s is the difference between the right ascensions
**     of the same point in two frames:  the two systems are the ICRS
**     and the CIP,CEO, and the point is the ascending node of the
**     respective equators.  The quantity s remains below 0.1 arcsecond
**     throughout 1900-2100.
**
**  3) The series used to compute s is in fact for s+XY/2, where X and Y
**     are the x and y components of the CIP unit vector;  this series is
**     more compact than a direct series for s would be.  This function
**     requires X,Y to be supplied by the caller, who is responsible for
**     providing values that are consistent with the supplied date.
**
**  4) The model is consistent with the "P03" precession (Capitaine et
**     al. 2003).
**
**  Called:  slaDrange
**
**  Defined in slamac.h:  D2PI, DAS2R
**
**  References:
**
**     Capitaine, N., Wallace, P.T. & Chapront, J., 2003, Astronomy &
**     Astrophysics, 432, 355-357
**
**     McCarthy, D.D., Petit, G. (eds.) 2004, IERS Conventions (2003),
**     IERS Technical Note No. 32, BKG
**
**  Last revision:   22 October 2006
**
**  Copyright P.T.Wallace.  All rights reserved.
*/

#define DJC 36525.0            /* Days per Julian century */
#define DJM0 51544.5           /* Reference epoch (J2000), MJD */
#define DUAS2R ( DAS2R / 1e6 ) /* Microarcsec to radians */

{
/* Fundamental arguments: l,l',F,D,Om,LVe,LE,pA */
#define NFA 8
   double fa[NFA];

/* One term in the series for s+XY/2 */

   struct sterm {
      int nfa[NFA];  /* Amount of each fundamental argument */
      double s;      /* Amplitude of sine term */
      double c;      /* Amplitude of cosine term */
   };

/* The t^0 terms */
   static struct sterm s0[] = {
      {{0,  0,  0,  0,  0,  0,  0,  0},    0.00,    94.00},
      {{0,  0,  0,  0,  1,  0,  0,  0},-2640.73,     0.39},
      {{0,  0,  0,  0,  2,  0,  0,  0},  -63.53,     0.02},
      {{0,  0,  2, -2,  3,  0,  0,  0},  -11.75,    -0.01},
      {{0,  0,  2, -2,  1,  0,  0,  0},  -11.21,    -0.01},
      {{0,  0,  2, -2,  2,  0,  0,  0},    4.57,     0.00},
      {{0,  0,  2,  0,  3,  0,  0,  0},   -2.02,     0.00},
      {{0,  0,  2,  0,  1,  0,  0,  0},   -1.98,     0.00},
      {{0,  0,  0,  0,  3,  0,  0,  0},    1.72,     0.00},
      {{0,  1,  0,  0,  1,  0,  0,  0},    1.41,     0.01},
      {{0,  1,  0,  0, -1,  0,  0,  0},    1.26,     0.01},
      {{1,  0,  0,  0, -1,  0,  0,  0},    0.63,     0.00},
      {{1,  0,  0,  0,  1,  0,  0,  0},    0.63,     0.00},
      {{0,  1,  2, -2,  3,  0,  0,  0},   -0.46,     0.00},
      {{0,  1,  2, -2,  1,  0,  0,  0},   -0.45,     0.00},
      {{0,  0,  4, -4,  4,  0,  0,  0},   -0.36,     0.00},
      {{0,  0,  1, -1,  1, -8, 12,  0},    0.24,     0.12},
      {{0,  0,  2,  0,  0,  0,  0,  0},   -0.32,     0.00},
      {{0,  0,  2,  0,  2,  0,  0,  0},   -0.28,     0.00},
      {{1,  0,  2,  0,  3,  0,  0,  0},   -0.27,     0.00},
      {{1,  0,  2,  0,  1,  0,  0,  0},   -0.26,     0.00},
      {{0,  0,  2, -2,  0,  0,  0,  0},    0.21,     0.00},
      {{0,  1, -2,  2, -3,  0,  0,  0},   -0.19,     0.00},
      {{0,  1, -2,  2, -1,  0,  0,  0},   -0.18,     0.00},
      {{0,  0,  0,  0,  0,  8,-13, -1},    0.10,    -0.05},
      {{0,  0,  0,  2,  0,  0,  0,  0},   -0.15,     0.00},
      {{2,  0, -2,  0, -1,  0,  0,  0},    0.14,     0.00},
      {{0,  1,  2, -2,  2,  0,  0,  0},    0.14,     0.00},
      {{1,  0,  0, -2,  1,  0,  0,  0},   -0.14,     0.00},
      {{1,  0,  0, -2, -1,  0,  0,  0},   -0.14,     0.00},
      {{0,  0,  4, -2,  4,  0,  0,  0},   -0.13,     0.00},
      {{0,  0,  2, -2,  4,  0,  0,  0},    0.11,     0.00},
      {{1,  0, -2,  0, -3,  0,  0,  0},   -0.11,     0.00},
      {{1,  0, -2,  0, -1,  0,  0,  0},   -0.11,     0.00}
   };
#define N0 ( sizeof s0 / sizeof s0[0] )

/* The t^1 terms */
   static struct sterm s1[] = {
      {{0,  0,  0,  0,  0,  0,  0,  0},    0.00,  3808.65},
      {{0,  0,  0,  0,  2,  0,  0,  0},   -0.07,     3.57},
      {{0,  0,  0,  0,  1,  0,  0,  0},    1.73,    -0.03},
      {{0,  0,  2, -2,  3,  0,  0,  0},    0.00,     0.48}
   };
#define N1 ( sizeof s1 / sizeof s1[0] )

/* The t^2 terms */
   static struct sterm s2[] = {
      {{0,  0,  0,  0,  0,  0,  0,  0},    0.00,  -122.68},
      {{0,  0,  0,  0,  1,  0,  0,  0},  743.52,    -0.17},
      {{0,  0,  2, -2,  2,  0,  0,  0},   56.91,     0.06},
      {{0,  0,  2,  0,  2,  0,  0,  0},    9.84,    -0.01},
      {{0,  0,  0,  0,  2,  0,  0,  0},   -8.85,     0.01},
      {{0,  1,  0,  0,  0,  0,  0,  0},   -6.38,    -0.05},
      {{1,  0,  0,  0,  0,  0,  0,  0},   -3.07,     0.00},
      {{0,  1,  2, -2,  2,  0,  0,  0},    2.23,     0.00},
      {{0,  0,  2,  0,  1,  0,  0,  0},    1.67,     0.00},
      {{1,  0,  2,  0,  2,  0,  0,  0},    1.30,     0.00},
      {{0,  1, -2,  2, -2,  0,  0,  0},    0.93,     0.00},
      {{1,  0,  0, -2,  0,  0,  0,  0},    0.68,     0.00},
      {{0,  0,  2, -2,  1,  0,  0,  0},   -0.55,     0.00},
      {{1,  0, -2,  0, -2,  0,  0,  0},    0.53,     0.00},
      {{0,  0,  0,  2,  0,  0,  0,  0},   -0.27,     0.00},
      {{1,  0,  0,  0,  1,  0,  0,  0},   -0.27,     0.00},
      {{1,  0, -2, -2, -2,  0,  0,  0},   -0.26,     0.00},
      {{1,  0,  0,  0, -1,  0,  0,  0},   -0.25,     0.00},
      {{1,  0,  2,  0,  1,  0,  0,  0},    0.22,     0.00},
      {{2,  0,  0, -2,  0,  0,  0,  0},   -0.21,     0.00},
      {{2,  0, -2,  0, -1,  0,  0,  0},    0.20,     0.00},
      {{0,  0,  2,  2,  2,  0,  0,  0},    0.17,     0.00},
      {{2,  0,  2,  0,  2,  0,  0,  0},    0.13,     0.00},
      {{2,  0,  0,  0,  0,  0,  0,  0},   -0.13,     0.00},
      {{1,  0,  2, -2,  2,  0,  0,  0},   -0.12,     0.00},
      {{0,  0,  2,  0,  0,  0,  0,  0},   -0.11,     0.00}
   };
#define N2 ( sizeof s2 / sizeof s2[0] )

/* The t^3 terms */
   static struct sterm s3[] = {
      {{0,  0,  0,  0,  0,  0,  0,  0},    0.00,-72574.11},
      {{0,  0,  0,  0,  1,  0,  0,  0},    0.30,   -23.42},
      {{0,  0,  2, -2,  2,  0,  0,  0},   -0.03,    -1.46},
      {{0,  0,  2,  0,  2,  0,  0,  0},   -0.01,    -0.25},
      {{0,  0,  0,  0,  2,  0,  0,  0},    0.00,     0.23}
   };
#define N3 ( sizeof s3 / sizeof s3[0] )

/* The t^4 terms */
   static struct sterm s4[] = {
      {{0,  0,  0,  0,  0,  0,  0,  0},    0.00,    27.98},
      {{0,  0,  0,  0,  1,  0,  0,  0},   -0.26,    -0.01}
   };
#define N4 ( sizeof s4 / sizeof s4[0] )

/* The t^5 terms */
   static struct sterm s5[] = {
      {{0,  0,  0,  0,  0,  0,  0,  0},    0.00,    15.62}
   };
#define N5 ( sizeof s5 / sizeof s5[0] )

/* The series for s+XY/2 */
   struct series {
      struct sterm *terms;
      int nterms;
   } ss[] = {
      { s0, N0 },
      { s1, N1 },
      { s2, N2 },
      { s3, N3 },
      { s4, N4 },
      { s5, N5 }
   };
#define NORDER ( sizeof ss / sizeof ss[0] )

   int i, j, k;
   double t, w, a;
   struct sterm *p;


/* --------------------- */
/* Fundamental Arguments */
/* --------------------- */

/* Interval between fundamental epoch J2000.0 and current date (JC). */
   t = ( date - DJM0 ) / DJC;

/* Mean anomaly of the Moon. */
   fa[0] = slaDrange ( ( 485868.249036 +
                       ( 715923.2178 +
                       (     31.8792 +
                       (      0.051635 +
                       (     -0.00024470 )
                         * t ) * t ) * t ) * t ) * DAS2R
                         + fmod_ ( 1325.0*t, 1.0 ) * D2PI );

/* Mean anomaly of the Sun. */
   fa[1] = slaDrange ( ( 1287104.793048 +
                       ( 1292581.0481 +
                       (      -0.5532 +
                       (      +0.000136 +
                       (      -0.00001149 )
                       * t ) * t ) * t ) * t ) * DAS2R
                       + fmod_ ( 99.0*t, 1.0 ) * D2PI );

/* Mean longitude of the Moon minus mean longitude of the ascending */
/* node of the Moon.                                                */
   fa[2] = slaDrange ( (  335779.526232 +
                       (  295262.8478 +
                       (     -12.7512 +
                       (      -0.001037 +
                       (       0.00000417 )
                       * t ) * t ) * t ) * t ) * DAS2R
                       + fmod_ ( 1342.0*t, 1.0 ) * D2PI );

/* Mean elongation of the Moon from the Sun. */
   fa[3] = slaDrange ( ( 1072260.703692 +
                       ( 1105601.2090 +
                       (      -6.3706 +
                       (       0.006593 +
                       (      -0.00003169 )
                       * t ) * t ) * t ) * t ) * DAS2R
                       + fmod_ ( 1236.0*t, 1.0 ) * D2PI );

/* Mean longitude of the ascending node of the Moon. */
   fa[4] = slaDrange ( (  450160.398036 +
                       ( -482890.5431 +
                       (       7.4722 +
                       (       0.007702 +
                       (      -0.00005939 )
                       * t ) * t ) * t ) * t ) * DAS2R
                       + fmod_ ( -5.0*t, 1.0 ) * D2PI );

/* Mean longitude of Venus. */
   fa[5] = slaDrange ( 3.176146697 + 1021.3285546211 * t );

/* Mean longitude of Earth. */
   fa[6] = slaDrange ( 1.753470314 +  628.3075849991 * t );

/* General precession in longitude. */
   fa[7] =           ( 0.024381750 +    0.00000538691 * t ) * t;

/* -------------- */
/* Compute s+xy/2 */
/* -------------- */

   w = 0.0;
   for ( i = NORDER-1; i >= 0; i-- ) {
      w *= t;
      for ( j = ss[i].nterms-1; j >= 0; j-- ) {
         p = &ss[i].terms[j];
         a = 0.0;
         for ( k = 0; k < NFA; k++ ) {
            a += (double) p->nfa[k] * fa[k];
         }
         w += p->s*sin_(a) + p->c*cos_(a);
      }
   }

/* -------------- */
/* The quantity s */
/* -------------- */

   return ( w * DUAS2R - x*y/2.0 );
}
