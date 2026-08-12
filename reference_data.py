"""Curated engineering reference sheet, split into sections.

The whole sheet is sent when no discipline section is selected. When one is,
only the core plus that discipline's tables go into the prompt -- which is what
lets this file be large without making every turn expensive.
"""

PREAMBLE = """\
REFERENCE DATA (curated handbook/typical values -- always verify against the actual
material certification, fastener specification, or drawing callout before use in a
flight design; these are starting points, not certified values).

These tables exist so specific numbers do not have to be recalled from memory. Use
them in preference to recalled values where they overlap. They are a lookup aid, not
a constraint on method: choose whatever analysis approach the problem warrants, and
say so when a problem needs data that is not here.
"""

CORE = """\
## Units and Constants

1 ksi = 6.895 MPa | 1 psi = 6895 Pa | 1 lbf = 4.448 N | 1 in-lb = 0.1130 Nm
1 ft-lb = 1.356 Nm | 1 in = 25.4 mm | 1 lbm = 0.4536 kg | 1 slug = 14.59 kg
1 W = 3.412 BTU/hr | 1 g/cm3 = 0.0361 lb/in3 | dT(F) = 1.8 * dT(C)
g = 9.807 m/s2 = 386.1 in/s2 | Stefan-Boltzmann sigma = 5.670e-8 W/m2-K4
Solar constant (1 AU) = 1361 W/m2 | R_universal = 8.314 J/mol-K
Steel E = 200 GPa = 29e6 psi | Aluminum E = 69 GPa = 10e6 psi
Titanium E = 114 GPa = 16.5e6 psi | G = E/(2*(1+nu))

## Margins and Factors

Margin of safety MS = allowable/(FS * applied) - 1. Report MS >= 0 as passing and
always state which allowable (yield or ultimate) and which factor were used.
Limit load = maximum expected in service. Ultimate load = limit x ultimate factor.
Typical aerospace factors (verify against the governing program spec):
yield 1.25, ultimate 1.4 for metallic structure; 2.0 ultimate for pressure vessels;
1.5-2.0 for composites and bonded joints; higher for crewed systems.
A-basis allowable: 99% of the population exceeds it with 95% confidence (use for
single load path). B-basis: 90% with 95% confidence (redundant load paths).
Typical/handbook values are neither, and are not certifiable on their own.
"""

SECTIONS: dict[str, str] = {}

SECTIONS["metals"] = """\
## Metals (room temperature, typical)

| Material | rho (g/cm3) | E (GPa) | nu | Sy (MPa) | Su (MPa) | elong % | CTE (um/m-C) | k (W/m-K) | cp (J/kg-K) |
|---|---|---|---|---|---|---|---|---|---|
| Al 6061-T6 | 2.70 | 68.9 | 0.33 | 276 | 310 | 12 | 23.6 | 167 | 896 |
| Al 6061-T4 | 2.70 | 68.9 | 0.33 | 145 | 241 | 22 | 23.6 | 154 | 896 |
| Al 7075-T6 | 2.81 | 71.7 | 0.33 | 503 | 572 | 11 | 23.4 | 130 | 960 |
| Al 7075-T73 | 2.81 | 71.7 | 0.33 | 435 | 505 | 13 | 23.4 | 155 | 960 |
| Al 2024-T3 | 2.78 | 73.1 | 0.33 | 345 | 483 | 18 | 23.2 | 121 | 875 |
| Al 5052-H32 | 2.68 | 70.3 | 0.33 | 193 | 228 | 12 | 23.8 | 138 | 880 |
| Al 356-T6 (cast) | 2.68 | 72.4 | 0.33 | 205 | 262 | 5 | 21.5 | 151 | 963 |
| Ti-6Al-4V (ann.) | 4.43 | 113.8 | 0.342 | 880 | 950 | 14 | 8.6 | 6.7 | 526 |
| Ti Grade 2 (CP) | 4.51 | 105 | 0.34 | 275 | 345 | 20 | 8.6 | 16.4 | 523 |
| 17-4PH H900 | 7.75 | 196 | 0.27 | 1170 | 1310 | 10 | 10.8 | 18 | 460 |
| 17-4PH H1075 | 7.75 | 196 | 0.27 | 1000 | 1070 | 13 | 10.8 | 18 | 460 |
| SS 304 (ann.) | 8.00 | 193 | 0.29 | 215 | 505 | 40 | 17.3 | 16.2 | 500 |
| SS 316 (ann.) | 8.00 | 193 | 0.29 | 240 | 580 | 40 | 16.0 | 16.3 | 500 |
| A286 (aged) | 7.94 | 201 | 0.31 | 690 | 1000 | 15 | 16.9 | 12.6 | 460 |
| 4130 steel (norm.) | 7.85 | 205 | 0.29 | 460 | 670 | 25 | 12.2 | 42.7 | 477 |
| 4340 steel (Q&T) | 7.85 | 205 | 0.29 | 1030 | 1110 | 14 | 12.3 | 44.5 | 475 |
| A36 mild steel | 7.85 | 200 | 0.26 | 250 | 400 | 23 | 11.7 | 51.9 | 486 |
| Inconel 718 (aged) | 8.19 | 200 | 0.29 | 1030 | 1275 | 12 | 13.0 | 11.4 | 435 |
| Invar 36 | 8.05 | 141 | 0.29 | 276 | 483 | 30 | 1.3 | 10.2 | 515 |
| Kovar | 8.36 | 138 | 0.32 | 340 | 520 | 30 | 5.9 | 17.3 | 439 |
| Mg AZ31B | 1.77 | 45 | 0.35 | 220 | 290 | 15 | 26.0 | 96 | 1000 |
| Cu C110 | 8.96 | 117 | 0.34 | 70 | 220 | 45 | 17.0 | 391 | 385 |
| Brass C360 | 8.50 | 97 | 0.34 | 310 | 470 | 25 | 20.5 | 115 | 380 |
| BeCu C17200 (AT) | 8.25 | 128 | 0.30 | 1030 | 1240 | 4 | 17.0 | 105 | 420 |

Plane-strain fracture toughness K_IC (MPa-sqrt(m), typical): Al 6061-T6 ~29;
Al 7075-T6 ~24; Al 7075-T73 ~33; Al 2024-T3 ~34; Ti-6Al-4V ~75; 4340 (Q&T) ~50;
17-4PH H900 ~45; 300-series CRES very high (>100, generally not toughness limited).

Temper and condition designations:
- T4 solution treated and naturally aged; T6 solution treated and artificially aged
  (peak strength); T651 T6 plus stress relief by stretching (use for plate that will
  be heavily machined -- it minimises distortion); T73 overaged, ~10-15% below T6
  strength but far better stress corrosion resistance.
- H32/H34 strain hardened and stabilised (non-heat-treatable 5xxx alloys).
- Annealed / normalised / Q&T for steels; H900-H1150 are 17-4PH aging conditions,
  with higher numbers meaning higher aging temperature, lower strength, more toughness.

Practical notes: 6061 is the default for machined structure -- weldable, corrosion
resistant, anodises well. 7075 is for strength-critical parts but is not practically
weldable and is SCC-sensitive in T6. 2024 has good fatigue behaviour and is common in
sheet. 6061-T6 welded drops toward annealed strength in the heat-affected zone
(design the weld zone near 165 MPa yield unless re-heat treated); filler 4043 for
general use, 5356 for higher strength and better anodising match. Properties in thick
plate are direction-dependent -- short-transverse is the weak direction and is where
SCC initiates.
"""

SECTIONS["polymers"] = """\
## Polymers and Non-Metals (typical)

| Material | rho (g/cm3) | E (GPa) | Strength (MPa) | CTE (um/m-C) | Max cont. T (C) | Notes |
|---|---|---|---|---|---|---|
| PEEK | 1.32 | 3.6 | 100 | 47 | 250 | excellent all-round, expensive |
| Ultem 1000 (PEI) | 1.27 | 3.2 | 105 | 56 | 170 | good vacuum/radiation behaviour |
| Vespel SP-1 | 1.43 | 3.1 | 86 | 54 | 290 | vacuum bearings/bushings |
| Delrin / POM | 1.41 | 3.1 | 70 | 110 | 90 | machines beautifully, poor bonding |
| Nylon 6/6 | 1.14 | 2.8 | 82 | 80 | 100 | absorbs moisture, swells ~0.5% |
| PTFE | 2.20 | 0.5 | 23 | 135 | 260 | lowest friction, creeps badly |
| Polycarbonate | 1.20 | 2.4 | 62 | 68 | 120 | tough, notch sensitive, solvent crazing |
| ABS | 1.05 | 2.3 | 45 | 90 | 85 | prototypes, not structural |
| PMMA (acrylic) | 1.18 | 3.0 | 70 | 70 | 80 | brittle, optically clear |
| UHMWPE | 0.94 | 0.7 | 40 | 150 | 80 | wear surfaces |
| G10 / FR4 | 1.85 | 24 (flex) | 310 (flex) | 11-16 | 130 | structural insulator, low k |
| Torlon (PAI) | 1.42 | 4.5 | 165 | 31 | 260 | highest strength thermoplastic |

Polymer design rules: creep under sustained load is the usual failure mode, so
design constant-stress parts to roughly 25-33% of short-term strength. CTE is an
order of magnitude above metals -- a plastic part bolted to aluminium will move
relative to it, so use slotted or clearance features. Most polymers lose stiffness
sharply as temperature approaches Tg. Nylon's moisture absorption makes it a poor
choice for precision or vacuum work.

Adhesives (typical): Hysol EA9394 structural epoxy, lap shear ~30 MPa, service to
~150 C, space qualified. Hysol EA9309 toughened, higher peel. Loctite 242 removable
threadlocker, 271 permanent. Bond line thickness of 0.1-0.25 mm is typical; joints
should be designed for shear, never for peel or cleavage.
"""

SECTIONS["composites"] = """\
## Composites

Unidirectional carbon/epoxy prepreg (aerospace grade, ~60% fibre volume):
- E1 150-165 GPa, E2 8-10 GPa, G12 4-5 GPa, nu12 ~0.30
- Longitudinal tension 2000-2700 MPa, longitudinal compression 1200-1700 MPa
- Transverse tension 50-80 MPa, transverse compression 200-250 MPa
- In-plane shear 90-120 MPa, interlaminar shear strength (ILSS) 80-100 MPa
- CTE1 -0.5 to 0 um/m-C, CTE2 25-30 um/m-C
- Typical cured ply thickness 0.125 mm (0.005 in); density ~1.6 g/cm3
- High-modulus pitch fibre variants reach E1 350-550 GPa at lower strength, used
  for dimensionally stable optical benches

Woven carbon fabric (plain/twill, balanced): E ~70 GPa in both in-plane directions,
tensile strength 600-800 MPa, ply thickness 0.20-0.25 mm.
E-glass/epoxy UD: E1 ~45 GPa, strength ~1100 MPa, density 2.0 g/cm3, RF transparent.
Quasi-isotropic carbon laminate [0/45/-45/90]s: E ~50-55 GPa, CTE ~2-3 um/m-C.

Aluminium honeycomb core 5052, 3/16 cell, 0.002 in foil: density ~50 kg/m3, bare
compressive strength ~2.2 MPa, L-direction shear ~1.5 MPa, W-direction ~0.9 MPa.
Nomex honeycomb: lower strength, non-conductive, common in RF-sensitive structure.
Sandwich panel bending stiffness scales with the square of core thickness -- doubling
core thickness is roughly four times stiffer at almost no mass penalty.

Layup rules: symmetric about the midplane to avoid extension-bending coupling;
balanced (+theta for every -theta) to avoid extension-shear coupling; limit adjacent
same-angle plies to about four to control matrix cracking; keep at least ~10% of
plies in each of 0/+45/-45/90 for bolted or damage-tolerant structure; put 45-degree
plies on the outside for impact and handling; taper ply drops no steeper than about
1:20 to limit delamination.

Failure theories:
- Maximum Stress / Maximum Strain: component-by-component, no interaction between
  stress components. Useful for screening.
- Tsai-Hill: single interactive index over in-plane stresses; does not separate
  tension from compression allowables.
- Tsai-Wu: general quadratic interactive criterion; distinguishes tension from
  compression; the most commonly used interactive criterion in practice.
- Puck and LaRC criteria distinguish fibre failure from matrix failure modes and are
  preferred where the failure mechanism matters.
- Report first-ply-failure and last-ply-failure separately and state which governs.

Environmental knockdowns are normal practice: hot/wet conditioning, barely visible
impact damage (BVID), and free-edge effects. Composites have negligible through-
thickness strength -- flag any design that loads a laminate or bondline in peel.
"""

SECTIONS["stress"] = """\
## Stress Analysis Formulas

Axial sigma = P/A. Bending sigma = M*c/I. Torsion (round) tau = T*r/J.
Transverse shear: rectangular tau_max = 1.5*V/A; solid round tau_max = 1.33*V/A;
thin-wall tube tau_max ~= 2*V/A. Bearing stress = P/(d*t).
Thin-wall pressure vessel (t < r/10): cylinder hoop = p*r/t, longitudinal = p*r/(2t);
sphere = p*r/(2t). Hoop governs a cylinder, so cylinders split along their length.

Section properties:
- Rectangle: I = b*h^3/12, Z = b*h^2/6, A = b*h
- Solid round: I = pi*d^4/64, J = pi*d^4/32, Z = pi*d^3/32
- Tube: I = pi*(D^4 - d^4)/64, J = 2*I
- Thin-wall tube (mean radius R, wall t): I ~= pi*R^3*t, J ~= 2*pi*R^3*t
- Parallel axis theorem: I = I_c + A*d^2

Beam cases (E*I constant):
| Case | Max deflection | Max moment |
|---|---|---|
| Cantilever, end load P | P*L^3/(3EI) | P*L |
| Cantilever, UDL w | w*L^4/(8EI) | w*L^2/2 |
| Simply supported, centre P | P*L^3/(48EI) | P*L/4 |
| Simply supported, UDL w | 5*w*L^4/(384EI) | w*L^2/8 |
| Fixed-fixed, centre P | P*L^3/(192EI) | P*L/8 |
| Fixed-fixed, UDL w | w*L^4/(384EI) | w*L^2/12 (ends) |
| Propped cantilever, UDL w | w*L^4/(185EI) | w*L^2/8 (fixed end) |

Torsional stiffness: theta = T*L/(G*J). Open thin-wall sections (channels, angles,
split tubes) have J orders of magnitude lower than closed sections -- never treat a
C-channel as torsionally stiff.

Euler buckling: P_cr = pi^2*E*I/(K*L)^2, K = 1.0 pinned-pinned, 0.5 fixed-fixed,
0.7 fixed-pinned, 2.0 fixed-free. Valid only above the critical slenderness ratio;
below it use the Johnson parabolic relation or yielding. Also check local buckling
and crippling of thin flanges and webs, and plate buckling for panels.

Combined stress: von Mises (2D) sigma_v = sqrt(sigma_x^2 - sigma_x*sigma_y +
sigma_y^2 + 3*tau_xy^2). Shaft in bending plus torsion: sigma_v = sqrt(sigma_b^2 +
3*tau^2). Use maximum principal stress for brittle materials, von Mises for ductile.

Stress concentration Kt (nominal-stress basis), typical:
round hole in wide plate, uniaxial tension 3.0; elliptical hole 1 + 2a/b;
shoulder fillet r/d = 0.05 ~2.2, r/d = 0.1 ~1.8, r/d = 0.2 ~1.5;
U-notch r/d = 0.1 ~2.3; keyway in shaft ~2.0 bending, ~3.0 torsion;
threads ~2.5-3.5 at the root. Ductile metals tolerate Kt under static load through
local yielding; under fatigue they do not.

Press fit: interference typically 0.0005-0.0015 in per inch of diameter. Contact
pressure follows from Lame's thick-cylinder equations; check hoop stress in the
outer member and the temperature at which the fit is lost from CTE mismatch.
"""

SECTIONS["fatigue"] = """\
## Fatigue and Fracture

Steel endurance limit Se' ~= 0.5*Su, capped near 700 MPa. Aluminium and titanium
have no true endurance limit; use fatigue strength at 5e8 cycles, roughly
0.3-0.4*Su for aluminium.
Corrected endurance Se = ka*kb*kc*kd*ke*Se' (surface finish, size, load type,
temperature, reliability). Surface finish is usually the largest single factor:
a machined surface may retain ~0.8 of the polished value, hot-rolled ~0.5, forged
as-cast ~0.35.

Mean stress corrections: Goodman sigma_a/Se + sigma_m/Su = 1/n (standard for
ductile metals); Soderberg substitutes Sy for Su (conservative, guarantees no
yielding); Gerber is parabolic and less conservative. Compressive mean stress is
beneficial -- this is why shot peening and cold expansion of holes work.

Cumulative damage: Miner's rule sum(n_i/N_i) = 1 at failure. Apply across the full
life including qualification and acceptance testing, not just service.

Fracture mechanics: K = Y*sigma*sqrt(pi*a); fast fracture when K reaches K_IC.
Critical crack size a_c = (1/pi)*(K_IC/(Y*sigma))^2. Crack growth follows Paris law
da/dN = C*(dK)^m, with m typically 3-4 for steels and aluminium.
Damage-tolerant design assumes a crack the size of the inspection detection limit
already exists and shows the structure survives to the next inspection.

Practical drivers, in order: stress concentrations, surface finish, residual stress,
and environment. A polished generous fillet in a weaker alloy routinely outperforms
a sharp corner in a stronger one. Welds, threads, and holes are where fatigue
cracks start.
"""

SECTIONS["fasteners"] = """\
## Fasteners and Bolted Joints

Preload: T = K*D*F_preload. K ~= 0.20 dry/as-received steel, 0.15 lubricated or
cad/lube plated, 0.28 unplated and dirty, ~0.10 with anti-seize on CRES.
Torque control alone is only about +/-25-35% accurate on preload; angle control or
direct stretch measurement is far better where preload matters.
Typical target preload = 65-75% of proof/yield for reusable joints.
Proof load ~= 0.90 * Sy for most fastener standards.

Tensile stress area:
| Thread | At (in2) | Thread | At (mm2) |
|---|---|---|---|
| #2-56 | 0.00370 | M2 x 0.4 | 2.07 |
| #4-40 | 0.00604 | M2.5 x 0.45 | 3.39 |
| #6-32 | 0.00909 | M3 x 0.5 | 5.03 |
| #8-32 | 0.01400 | M4 x 0.7 | 8.78 |
| #10-32 | 0.02000 | M5 x 0.8 | 14.2 |
| 1/4-20 | 0.03180 | M6 x 1.0 | 20.1 |
| 1/4-28 | 0.03640 | M8 x 1.25 | 36.6 |
| 5/16-18 | 0.05240 | M10 x 1.5 | 58.0 |
| 3/8-16 | 0.07750 | M12 x 1.75 | 84.3 |

Fastener material strengths (typical Su): A286 CRES 1100-1300 MPa; 300-series CRES
515-620 MPa; Ti-6Al-4V 950 MPa; alloy steel Grade 8 / 180 ksi 1240 MPa; NAS/MS
socket head cap screws commonly 180 ksi; metric class 8.8 = 830 MPa, 10.9 = 1040,
12.9 = 1220. A286 is the usual spaceflight default: strong, corrosion resistant,
non-magnetic, needs no plating. Single shear allowable ~= 0.6 * tensile allowable.

Torque, typical dry, generic reference class -- verify against the actual spec,
plating, and lubrication:
| Size | 300-series CRES | A286 / alloy steel |
|---|---|---|
| #4-40 | 4-5 in-lb | 8-9 in-lb |
| #6-32 | 9-10 in-lb | 16-18 in-lb |
| #8-32 | 18-20 in-lb | 30-33 in-lb |
| #10-32 | 30-32 in-lb | 55-60 in-lb |
| 1/4-20 | 65-75 in-lb | 95-100 in-lb |
| 5/16-18 | 130-145 in-lb | 200 in-lb |
| M3 | 1.0-1.3 Nm | 1.9-2.2 Nm |
| M4 | 2.5-3.0 Nm | 4.3-4.8 Nm |
| M5 | 5.0-6.0 Nm | 8.5-9.5 Nm |
| M6 | 8.0-10.0 Nm | 14-16 Nm |
| M8 | 20-24 Nm | 34-38 Nm |

Joint mechanics: the bolt carries only the stiffness-ratio share of an external
tensile load, C = k_bolt/(k_bolt + k_members), typically 0.1-0.3 for metal joints.
Bolt load = preload + C * external load. Separation occurs when external load
exceeds preload/(1 - C). A properly preloaded joint sees very little fatigue load;
loss of preload is the usual root cause of bolt fatigue failure.
Friction joints carrying shear: capacity = n * mu * preload, with mu ~0.2 for dry
machined aluminium. Do not rely on both friction and bolt shear simultaneously.

Thread engagement: minimum 1xD into steel, 1.5-2xD into aluminium, 2-3xD into
plastics. Beyond about 2xD adds little, since the first three engaged threads carry
most of the load. Use helicoils or keenserts in aluminium and plastics, and always
where the joint will be disassembled repeatedly.

Tap drill (75% thread) and clearance holes:
| Thread | Tap drill | Clearance (close / normal) |
|---|---|---|
| #4-40 | #43 (0.089) | 0.116 / 0.128 |
| #6-32 | #36 (0.1065) | 0.144 / 0.154 |
| #8-32 | #29 (0.136) | 0.170 / 0.180 |
| #10-32 | #21 (0.159) | 0.196 / 0.204 |
| 1/4-20 | #7 (0.201) | 0.257 / 0.266 |
| 5/16-18 | F (0.257) | 0.323 / 0.332 |
| 3/8-16 | 5/16 (0.3125) | 0.386 / 0.397 |
| M3 x 0.5 | 2.5 mm | 3.2 / 3.4 |
| M4 x 0.7 | 3.3 mm | 4.3 / 4.5 |
| M5 x 0.8 | 4.2 mm | 5.3 / 5.5 |
| M6 x 1.0 | 5.0 mm | 6.4 / 6.6 |
| M8 x 1.25 | 6.8 mm | 8.4 / 9.0 |

Edge distance and spacing: minimum edge distance 2xD to fastener centre (1.5xD
absolute minimum), spacing 4xD typical. Below this, tear-out and bearing govern.

Locking: prevailing-torque nuts (nylon insert limited to ~120 C; all-metal for
higher), thread locker (Loctite 242 removable, 271 permanent), safety wire, staking,
and lock washers. Split lock washers are largely ineffective under vibration.
Spaceflight joints normally require a positive locking feature that does not depend
on friction alone, plus a preload verification method.
"""

SECTIONS["fits"] = """\
## Fits, Tolerances, and Process Capability

ISO hole-basis fits: H7/g6 sliding; H7/h6 locational clearance; H7/k6 transition
(light tap); H7/n6 tight transition; H7/p6 press; H7/s6 heavy press or shrink.
Running fits need clearance for thermal growth -- check the CTE difference over the
full temperature range before choosing.

Achievable tolerances, typical:
| Process | Typical | Precision |
|---|---|---|
| CNC milling/turning | +/-0.005 in (0.13 mm) | +/-0.001 in (0.025 mm) |
| Reaming | +/-0.0005 in | +/-0.0002 in |
| Grinding | +/-0.0005 in | +/-0.0001 in |
| Sheet metal bend | +/-0.015 in, angle +/-1 deg | +/-0.010 in |
| Laser / waterjet cut | +/-0.005 in | +/-0.003 in |
| Sand casting | +/-0.030 in | -- |
| Investment casting | +/-0.010 in | +/-0.005 in |
| Injection moulding | +/-0.005 in | +/-0.002 in |
| FDM 3D print | +/-0.010 in | -- |
| SLA / SLS | +/-0.005 in | -- |
| DMLS metal AM | +/-0.005 in + 0.1% | -- |

Surface finish Ra: rough machining 125-250 uin; finish machining 32-63 uin; typical
mill finish 63 uin (1.6 um); grinding 8-32 uin; lapping/polishing 1-8 uin.
Sealing surfaces usually need 32 uin or better; O-ring grooves 32 uin sides and
16-32 uin on the sealing surface; fatigue-critical surfaces benefit below 32 uin.

Process capability: Cp = (USL - LSL)/(6*sigma); Cpk accounts for centring. Cpk of
1.33 is the usual minimum for a capable process, 1.67 for critical characteristics.
RSS stackups are only valid when contributors are independent and processes are in
control at that capability.

Sheet metal gauges (nominal thickness, inches):
| Gauge | Steel | Aluminium |
|---|---|---|
| 22 | 0.0299 | 0.0253 |
| 20 | 0.0359 | 0.0320 |
| 18 | 0.0478 | 0.0403 |
| 16 | 0.0598 | 0.0508 |
| 14 | 0.0747 | 0.0641 |
| 12 | 0.1046 | 0.0808 |
| 10 | 0.1345 | 0.1019 |

O-ring glands (static): 20-30% squeeze for face seals, 15-25% for radial; gland
fill 75-85% by volume to leave room for thermal expansion and swell; surface finish
32 uin; avoid spiral failure by keeping dynamic seals well lubricated and within
speed limits.
"""

SECTIONS["gdt"] = """\
## GD&T (ASME Y14.5)

Form (no datum): Straightness, Flatness, Circularity, Cylindricity
Profile: Profile of a Line, Profile of a Surface
Orientation: Angularity, Perpendicularity, Parallelism
Location: Position, Concentricity, Symmetry (the last two are deprecated in
Y14.5-2018 -- prefer position or profile)
Runout: Circular Runout, Total Runout

Modifiers and rules:
- MMC (M) yields bonus tolerance as the feature departs from MMC; use where the
  requirement is assembly clearance. LMC (L) is used for wall thickness and minimum
  material cases. RFS is the default when no modifier is shown.
- Rule #1: a feature of size at MMC must have perfect form, unless overridden.
- Datum precedence order defines the constraint sequence -- a primary planar datum
  constrains 3 degrees of freedom, secondary 2, tertiary 1. Changing the order
  changes the meaning of every downstream callout.
- Datum targets are used where a full surface is not a realistic locating feature
  (castings, weldments, large sheet parts).
- Composite position tolerances control pattern location and feature-to-feature
  spacing separately, with the tighter lower segment applying within the pattern.

Fastener formulas:
- Fixed fastener (one part threaded): T = (H - F)/2 applied to each part.
- Floating fastener (both parts clearance): T = H - F, split between the parts.
  H = minimum clearance hole diameter, F = maximum fastener diameter.
- Bonus tolerance = actual feature size - MMC size, for holes called at MMC.
- Projected tolerance zone should be used for threaded holes and press-fit pins, or
  the fastener can still interfere despite an in-tolerance hole.

Stackups: worst case sums tolerances arithmetically and guarantees assembly at the
cost of tight tolerances. RSS uses sqrt(sum of squares), gives a looser and cheaper
result, and is legitimate only for statistically independent, in-control processes.
Draw the loop, identify the dominant contributor, and spend tolerance money there.
Every tolerance should trace to a function -- fit, seal, align, carry load, or
assemble. A tolerance with no functional justification is pure cost.
"""

SECTIONS["thermal"] = """\
## Thermal

Conduction q = k*A*dT/L; thermal resistance R = L/(k*A); resistances add in series.
Convection q = h*A*dT. Typical h: natural convection in air 5-25 W/m2-K; forced air
25-250; liquid water 500-10000. In vacuum, convection is zero -- conduction and
radiation carry everything.
Radiation q = eps*sigma*A*F*(T1^4 - T2^4); view factor F and area matter as much as
emissivity. Radiation only becomes competitive with conduction at higher absolute
temperatures, but in vacuum it is often the only path out.
Transient: Biot number Bi = h*L/k; Bi < 0.1 justifies lumped capacitance.
Time constant tau = rho*c*V/(h*A). Thermal diffusivity alpha = k/(rho*c).
Thermal stress, fully constrained: sigma = E*alpha*dT. Between two joined materials
the driving term is the CTE difference times the temperature swing.

Bolted interface conductance is finite and highly variable: bare aluminium-to-
aluminium joints run roughly 500-3000 W/m2-K depending on preload, flatness, and
finish. Thermal gap fillers or indium foil raise it substantially. This joint
resistance, not the bulk material, is usually the dominant term -- never assume
perfect contact.

Optical properties (solar absorptivity alpha / IR emissivity eps):
| Surface | alpha | eps |
|---|---|---|
| Polished aluminium | 0.15 | 0.05 |
| Alodine / chem film | 0.35 | 0.10 |
| Black anodise | 0.88 | 0.88 |
| Clear anodise | 0.30 | 0.84 |
| White paint (Z93) | 0.17 | 0.92 |
| Black paint (Z306) | 0.95 | 0.90 |
| Kapton, 1 mil, alum. backed | 0.40 | 0.80 |
| Silvered Teflon (OSR) | 0.08 | 0.80 |
| Solar cell (typical) | 0.75 | 0.83 |
| MLI blanket | -- | 0.01-0.03 effective |

Low alpha/eps runs cold, high runs hot. Most coatings degrade toward higher alpha
over mission life -- use end-of-life properties for hot cases and beginning-of-life
for cold cases. Radiator sizing starts from Q = eps*sigma*A*(T_rad^4 - T_sink^4);
deep space sink is ~4 K, but in LEO add Earth IR (~240 W/m2) and albedo (~30% of
solar). Always analyse both a hot case and a cold case, and carry the result through
to structural consequences: differential expansion, preload change, bondline stress,
and thermal cycling fatigue.
"""

SECTIONS["vibration"] = """\
## Vibrations and Dynamic Environments

fn = (1/2pi)*sqrt(k/m). Cantilever beam first mode fn = 0.560*sqrt(E*I/(m'*L^4));
simply supported fn = 1.571*sqrt(E*I/(m'*L^4)), where m' is mass per unit length.
Adding tip mass drops frequency fast; stiffening the root raises it fast.
Q = 1/(2*zeta). Bolted metallic structure typically Q = 10-20 (zeta 2.5-5%);
welded or monolithic structure is lower damped; damped/composite joints higher.

Random vibration: PSD is in g^2/Hz; overall Grms = sqrt(integral of PSD over the
band). Miles' equation for a single-degree-of-freedom response:
Grms_response = sqrt((pi/2)*fn*Q*PSD(fn)). This is a 1-sigma value -- design to
3-sigma (3*Grms) for peak load. Miles' equation assumes narrow-band single-mode
response; closely spaced modes or multi-mode participation require an FEM random
response analysis instead.

Random vibration failures are usually high-cycle fatigue rather than a single
overload. Estimate cycles as fn * duration and sum damage over qualification,
acceptance, and flight.

Environments are distinct and not interchangeable: sine sweep, random vibration,
acoustic, and pyro/mechanical shock (characterised by a shock response spectrum).
Shock is high-frequency and high-g but very short -- it damages brittle parts,
crystals, relays, and solder joints rather than primary structure.

Typical launch quasi-static loads: 10-20 g axial, 5-10 g lateral (vehicle specific).
Common secondary-payload requirement: first mode above 90-120 Hz. Keep coupled
subsystems separated in frequency by roughly a factor of two to avoid amplification.
Isolation only attenuates above sqrt(2) times the isolator natural frequency and
amplifies below it -- a poorly chosen isolator makes things worse.

Raising a first mode, in order of effectiveness: shorten the unsupported span, move
material away from the neutral axis, close open sections, stiffen the mounting
interface, remove or relocate tip mass. Adding thickness uniformly is usually the
least efficient option.
"""

SECTIONS["manufacturing"] = """\
## Manufacturing and DFM

Machining: minimum internal corner radius equals the cutter radius, so specify a
radius at least 1/3 of pocket depth to allow a stiff tool; avoid pocket depth beyond
about 4x cutter diameter (chatter); avoid deep narrow slots and undercuts; minimise
setups, since every refixture adds tolerance; support thin walls against deflection.
Minimum wall thickness roughly 0.8 mm in aluminium, 0.5 mm in steel.
Every additional setup, tight tolerance, and fine finish callout is real cost.

Sheet metal: minimum bend radius 1x thickness for 5052, 2-3x for 6061-T6 (which
cracks -- consider 5052, or bend in T4 and age afterwards); minimum flange length
about 4x thickness plus radius; hole-to-bend distance at least 2.5x thickness plus
radius; bend relief at the ends of partial bends. Bend allowance
BA = (pi/180)*angle*(R + K*t), K-factor typically 0.33-0.45. Bend across the grain
where possible.

Injection moulding: uniform wall thickness above all; 1-2 degrees draft minimum
(3+ for textured surfaces); core out thick sections to avoid sink and voids; ribs
40-60% of nominal wall thickness; radius all corners; plan the parting line and
gate location, because they determine where the weld lines and cosmetic defects go.

Additive: overhangs beyond about 45 degrees need support, and support removal needs
access; properties are anisotropic, with Z-direction strength commonly 50-80% of XY;
metal AM parts normally require stress relief, often HIP, and machined datum
surfaces for anything precision; internal channels must be drainable.

Welding: design for torch and electrode access; expect distortion and plan a fixture
or a post-weld machining allowance; heat-treatable aluminium alloys soften in the
HAZ; 7075 and 2024 are not practically weldable, so use fasteners or friction stir
welding. Common joints: butt, lap, tee, corner. Specify weld size and length rather
than "weld all around" by default.

Casting: uniform sections, generous fillets, draft on all vertical faces, and
machining allowance on functional surfaces. Expect porosity -- do not put a casting
in a single fatigue-critical load path without inspection requirements.

Cost drivers, in order: tolerance tightness, setup count, material removal volume,
surface finish requirements, and inspection burden. Give concrete alternatives, not
just criticism -- a radius to add, a feature to move to another face, a tolerance to
open up.
"""

SECTIONS["corrosion"] = """\
## Corrosion and Surface Treatment

Galvanic series in seawater, anodic (corrodes) to cathodic (protected):
magnesium, zinc, aluminium alloys, cadmium, mild steel, cast iron, 300-series CRES
(active), lead, tin, brass, copper, nickel, titanium, 300-series CRES (passive),
graphite, gold, platinum.
The anodic member of a couple corrodes, and the rate rises with electrolyte
conductivity and with a large cathode paired to a small anode. Keep couples within
roughly 0.25 V for wet environments (0.5 V for controlled indoor environments), or
isolate with a barrier, a sealant, or a compatible plating.

Carbon fibre is strongly cathodic and will aggressively corrode aluminium in contact
with it -- always isolate a carbon laminate from aluminium with a glass ply, a
sealant layer, or a titanium interface.

Common treatments:
| Treatment | Spec | Typical use |
|---|---|---|
| Anodise Type II (sulfuric) | MIL-A-8625 | general corrosion, dyeable, 0.0002-0.001 in |
| Anodise Type III (hardcoat) | MIL-A-8625 | wear surfaces, 0.002 in, reduces fatigue life |
| Chem film / alodine | MIL-DTL-5541 | corrosion protection while staying conductive |
| Passivation | AMS 2700 | CRES, restores the chromium oxide layer |
| Electroless nickel | AMS 2404 | uniform hard coating, good on complex shapes |
| Cadmium plate | -- | avoid: toxic, and outgasses/whiskers in vacuum |
| Dry film lube (MoS2) | AS5272 | vacuum-compatible lubrication |

Anodising builds thickness on all surfaces -- roughly half of it grows outward, so
account for it on close-fit features and threads. Hardcoat measurably reduces
fatigue life in aluminium and should be kept off fatigue-critical fillets.
Stress corrosion cracking: prefer 7075-T73 over T6, avoid sustained tension in the
short-transverse direction of thick high-strength aluminium plate, and avoid
hydrogen-embrittling processes on high-strength steel above about 1100 MPa.
"""

SECTIONS["space"] = """\
## Spaceflight-Specific Considerations

Outgassing per ASTM E595: acceptance limits are TML < 1.0% and CVCM < 0.10%. Check
the NASA outgassing database for the specific material, cure, and bake-out.
Avoid: pure tin, zinc, and cadmium plating (whisker growth causing shorts); PVC;
untreated nylon (moisture); non-space-grade silicones (CVCM); any lubricant with a
volatile carrier; unbaked adhesives near optics or detectors.
Generally acceptable: aluminium alloys, titanium, A286 and 300-series CRES, PEEK,
Ultem, Vespel, Kapton, space-qualified epoxies such as Hysol EA9394, MoS2 dry film.

Environment effects: atomic oxygen erodes polymers and exposed carbon in LEO, so
protect with coatings or choose resistant materials. UV degrades polymers and drives
coating alpha upward over life. Total ionising dose embrittles polymers and damages
electronics. Thermal cycling drives CTE-mismatch fatigue in bonded and bolted
joints, and is often the life-limiting environment for a structure that easily
survives launch.

Design practice: vent every enclosed volume so it does not burst or distort during
ascent (a common rule of thumb is about 1 in2 of vent area per 1000 in3 of volume,
properly sized from the vehicle's ascent depressurisation rate). Avoid trapped
volumes in blind threaded holes -- use vented fasteners or a vent slot. Provide
positive fastener locking that does not rely on friction. Avoid wet lubricants in
mechanisms; use dry film or space-qualified greases. Keep dissimilar-metal couples
isolated, since condensation during ground handling is where much corrosion starts.
Design for handling and integration loads too -- many flight hardware failures
happen in the cleanroom, not in flight.
"""

# Order used when assembling the full sheet.
SECTION_ORDER = (
    "metals",
    "polymers",
    "composites",
    "stress",
    "fatigue",
    "fasteners",
    "fits",
    "gdt",
    "thermal",
    "vibration",
    "manufacturing",
    "corrosion",
    "space",
)


# Keywords used to pick relevant tables when no discipline is selected.
# Sending all thirteen sections on every question is both slow and, on a small
# tokens-per-minute tier, larger than a single request is allowed to be.
SECTION_KEYWORDS: dict[str, tuple[str, ...]] = {
    "metals": (
        "aluminum", "aluminium", "6061", "7075", "2024", "5052", "titanium",
        "ti-6al-4v", "steel", "stainless", "17-4", "inconel", "invar", "alloy",
        "material", "yield", "modulus", "density", "temper", "anneal", "magnesium",
    ),
    "polymers": (
        "plastic", "polymer", "peek", "ultem", "delrin", "nylon", "ptfe",
        "polycarbonate", "abs", "acrylic", "g10", "vespel", "injection", "adhesive",
        "epoxy", "bond", "glue",
    ),
    "composites": (
        "composite", "laminate", "layup", "lay-up", "ply", "plies", "carbon fiber",
        "carbon fibre", "cfrp", "fiberglass", "fibreglass", "prepreg", "tsai",
        "honeycomb", "sandwich", "delamination", "resin",
    ),
    "stress": (
        "stress", "strain", "load", "force", "moment", "beam", "bending",
        "deflection", "buckling", "torsion", "shear", "bracket", "margin",
        "safety factor", "von mises", "section", "cantilever", "pressure vessel",
        "hoop", "reaction", "free body", "column",
    ),
    "fatigue": (
        "fatigue", "cycle", "cyclic", "endurance", "crack", "fracture", "goodman",
        "miner", "s-n", "life", "damage tolerance", "notch",
    ),
    "fasteners": (
        "fastener", "bolt", "screw", "torque", "preload", "thread", "nut",
        "washer", "helicoil", "insert", "tap", "joint", "clamp", "locking",
        "loctite", "a286", "socket head",
    ),
    "fits": (
        "tolerance", "fit", "clearance", "interference", "press fit", "gauge",
        "surface finish", "ra ", "roughness", "reamed", "o-ring", "gland",
        "capability", "cpk",
    ),
    "gdt": (
        "gd&t", "gdt", "datum", "feature control", "position tolerance", "profile",
        "flatness", "perpendicularity", "concentricity", "runout", "mmc", "lmc",
        "stackup", "stack-up", "y14.5", "drawing", "callout",
    ),
    "thermal": (
        "thermal", "temperature", "heat", "conduction", "convection", "radiation",
        "emissivity", "absorptivity", "radiator", "cte", "expansion", "cryo",
        "hot case", "cold case", "vacuum", "cooling", "dissipation", "watt",
    ),
    "vibration": (
        "vibration", "vibe", "random", "sine", "psd", "grms", "shock", "srs",
        "natural frequency", "mode", "modal", "resonance", "damping", "miles",
        "launch", "acoustic", "isolator", "dynamic",
    ),
    "manufacturing": (
        "machining", "machined", "manufacture", "manufacturing", "dfm", "mill",
        "lathe", "turning", "cnc", "sheet metal", "bend", "weld", "casting",
        "molding", "moulding", "3d print", "additive", "am ", "cost", "draft",
        "fixture", "setup",
    ),
    "corrosion": (
        "corrosion", "galvanic", "anodize", "anodise", "alodine", "passivation",
        "plating", "coating", "rust", "scc", "stress corrosion", "dissimilar",
        "finish spec",
    ),
    "space": (
        "space", "spacecraft", "satellite", "orbit", "leo", "geo", "vacuum",
        "outgassing", "astm e595", "tml", "cvcm", "atomic oxygen", "flight",
        "cubesat", "payload", "launch", "thermal cycling", "radiation dose",
    ),
}

# Used when a question matches nothing in particular.
DEFAULT_SECTIONS = ("metals", "stress", "fasteners")

MAX_AUTO_SECTIONS = 4


def select_sections(query: str, limit: int = MAX_AUTO_SECTIONS) -> tuple[str, ...]:
    """Pick the reference tables a free-form question actually needs.

    Deliberately simple keyword scoring: it only decides which reference tables
    ride along, and a wrong guess costs relevance, not correctness -- the model
    still has its own knowledge and can say what it needs.
    """
    text = (query or "").lower()
    if not text.strip():
        return DEFAULT_SECTIONS

    scores: list[tuple[int, str]] = []
    for section, words in SECTION_KEYWORDS.items():
        hits = sum(1 for word in words if word in text)
        if hits:
            scores.append((hits, section))

    if not scores:
        return DEFAULT_SECTIONS

    scores.sort(key=lambda pair: (-pair[0], SECTION_ORDER.index(pair[1])))
    chosen = [section for _, section in scores[:limit]]
    return tuple(s for s in SECTION_ORDER if s in chosen)


def build(sections: tuple[str, ...] | None = None) -> str:
    """Assemble the reference sheet.

    sections=None returns everything. Passing a subset returns the core plus
    just those sections, which is how a selected discipline keeps the prompt
    small while the underlying sheet stays large.
    """
    chosen = SECTION_ORDER if sections is None else [
        s for s in SECTION_ORDER if s in sections
    ]
    parts = [PREAMBLE, CORE] + [SECTIONS[name] for name in chosen]
    return "\n".join(parts)


# Full sheet, kept as a module-level name for backward compatibility.
REFERENCE_DATA = build()
