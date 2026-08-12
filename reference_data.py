REFERENCE_DATA = """\
REFERENCE DATA (curated, typical/handbook values -- always verify against the actual \
material certification, fastener specification, or drawing callout before use in a \
flight design; these are starting points, not certified values).

## Common Aerospace Metals (room temperature, typical values)

| Material                | Density (g/cm3) | E (GPa) | Yield (MPa) | UTS (MPa) | CTE (um/m-C) |
|-------------------------|------------------|---------|-------------|-----------|--------------|
| Aluminum 6061-T6        | 2.70             | 68.9    | 276         | 310       | 23.6         |
| Aluminum 7075-T6        | 2.81             | 71.7    | 503         | 572       | 23.4         |
| Titanium Ti-6Al-4V      | 4.43             | 113.8   | 880         | 950       | 8.6          |
| Stainless 17-4PH (H900) | 7.75             | 196     | 1170        | 1310      | 10.8         |

## Carbon Fiber / Epoxy, Unidirectional (typical aerospace-grade prepreg)

- Longitudinal modulus E1: 150-165 GPa
- Transverse modulus E2: 8-10 GPa
- In-plane shear modulus G12: 4-5 GPa
- Major Poisson's ratio v12: ~0.30
- Longitudinal tensile strength (0 deg fiber direction): 2000-2700 MPa
- Longitudinal CTE: -0.5 to 0 um/m-C (near-zero to slightly negative -- useful for \
dimensionally stable structures)

## Composite Failure Theories

- Maximum Stress: failure when any stress component exceeds its allowable in that \
direction; no interaction between stress components.
- Maximum Strain: same approach as Maximum Stress, applied to strain components.
- Tsai-Hill: single interactive failure index combining all in-plane stress components; \
more realistic than Max Stress/Strain under combined loading, but does not distinguish \
tension from compression allowables.
- Tsai-Wu: general quadratic interactive criterion; distinguishes tension vs. compression \
allowables; the most commonly used interactive criterion in practice.

## Standard Fastener Torque (typical dry/unlubricated, generic reference class -- verify \
against the actual fastener spec, plating, and lubrication before applying)

| Size    | Torque (in-lb) | Torque (Nm) |
|---------|----------------|-------------|
| #4-40   | 4-5            | 0.5-0.6     |
| #6-32   | 9-10           | 1.0-1.1     |
| #8-32   | 20             | 2.3         |
| 1/4-20  | 90-100         | 10.2-11.3   |
| 5/16-18 | 200            | 22.6        |
| M3      | --             | 1.0-1.3     |
| M4      | --             | 2.5-3.0     |
| M5      | --             | 5.0-6.0     |
| M6      | --             | 8.0-10.0    |

## GD&T Symbols (ASME Y14.5)

- Form: Straightness, Flatness, Circularity, Cylindricity
- Profile: Profile of a Line, Profile of a Surface
- Orientation: Angularity, Perpendicularity, Parallelism
- Location: Position, Concentricity, Symmetry
- Runout: Circular Runout, Total Runout
"""
