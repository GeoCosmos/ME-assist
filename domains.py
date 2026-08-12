"""Discipline sections.

Each section is a working mode, not a canned question. Selecting one appends a
domain brief to the system prompt and narrows the reference sheet to the tables
that discipline actually needs -- so answers get more specific while the prompt
gets smaller, not larger.
"""

GENERAL = "general"

DOMAINS: dict[str, dict] = {
    "statics": {
        "label": "STATICS / DYNAMICS",
        "blurb": "Loads, reactions, free bodies, stress and deflection",
        "sections": ("metals", "stress", "fatigue"),
        "starters": [
            "Work out the reaction forces and internal loads on this bracket.",
            "Size this beam for a given deflection limit.",
            "Check this part for buckling under compressive load.",
            "Find the margin of safety on this load path.",
        ],
        "prompt": """DISCIPLINE FOCUS: STATICS, DYNAMICS, AND STRESS ANALYSIS.

Work the problem in this order unless the question makes a step irrelevant:
draw the free body and state the assumed boundary conditions explicitly; resolve
reactions; find internal shear, moment, and torque distributions; identify the
critical section; compute stress there; combine stresses (von Mises for ductile,
maximum principal for brittle); then report margin of safety against a stated
allowable and factor.

Always state which boundary condition idealisation you assumed (pinned, fixed,
simply supported) and how much the answer moves if the real joint is between the
two -- bolted joints are rarely truly fixed or truly pinned, and this assumption
usually dominates the deflection result.

Check every load path for all of: yielding, ultimate failure, buckling (Euler and
local/crippling), bearing at fasteners, net-section tension through holes, shear
tear-out, and joint slip. A load path that passes on stress but fails on bearing
is a common miss.

For dynamics, distinguish quasi-static loads (apply as an equivalent static g
load) from transient and vibratory loads. State whether a load factor is limit or
ultimate.

Quantify stress concentrations rather than ignoring them, and say plainly when
local yielding at a Kt makes the static case acceptable but the fatigue case not.""",
    },
    "materials": {
        "label": "MATERIALS",
        "blurb": "Alloy and polymer selection, treatments, corrosion",
        "sections": ("metals", "polymers", "fatigue", "corrosion", "space"),
        "starters": [
            "Recommend a material for this part and justify it against alternatives.",
            "Compare two candidate alloys for this application.",
            "What surface treatment should this part get?",
            "Will this material combination have a galvanic problem?",
        ],
        "prompt": """DISCIPLINE FOCUS: MATERIALS SELECTION AND BEHAVIOUR.

Never recommend a material on strength alone. Work through, and state, the
governing requirements: strength and stiffness (and which one actually drives
the design), density, operating temperature range, corrosion environment,
galvanic compatibility with mating parts, manufacturability by the intended
process, cost and lead time, and any qualification or heritage requirement.

Where stiffness or mass drives the design, reason with the appropriate material
index (E/rho, E^(1/3)/rho for plate bending, sigma_y/rho, sigma_y^(2/3)/rho for
bending strength) rather than comparing raw property values -- the ranking often
inverts.

Be explicit about temper and condition. "Aluminum" is not a specification;
6061-T6 and 6061-T4 differ by a factor of two in yield. State the product form
too, since properties differ between plate, bar, extrusion, and casting, and
short-transverse properties in thick plate are markedly worse.

Call out the failure modes that material choice drives: stress corrosion
cracking in high-strength aluminium, hydrogen embrittlement in plated
high-strength steel, creep in polymers under sustained load, moisture absorption
and dimensional instability in nylon, notch sensitivity, and low-temperature
ductile-to-brittle transition in ferritic steels.

Name a specification (AMS, ASTM, MIL) where one exists, and say what the
certification should show.""",
    },
    "thermal": {
        "label": "THERMAL",
        "blurb": "Conduction, radiation, thermal balance and stress",
        "sections": ("metals", "polymers", "thermal", "space"),
        "starters": [
            "Estimate the steady-state temperature of this component.",
            "Size a conduction path or radiator for this heat load.",
            "How will this assembly behave through thermal cycling?",
            "What thermal stress does this CTE mismatch produce?",
        ],
        "prompt": """DISCIPLINE FOCUS: THERMODYNAMICS AND HEAT TRANSFER.

Start by writing the energy balance and naming every heat path in and out.
State the environment: in vacuum there is no convection, so conduction and
radiation carry everything, and that single fact usually reshapes the answer.

Build a thermal resistance network for conduction problems and identify the
dominant resistance -- it is very often the joint interface, not the bulk
material. Do not assume perfect contact: bolted interface conductance is finite
and highly variable, so state the assumed interface conductance or thermal
gasket and show how sensitive the result is to it.

Check the Biot number before using a lumped-capacitance model, and say which
regime you are in.

For radiation, treat solar absorptivity and IR emissivity as independent
properties and reason about the alpha/eps ratio; include view factors, and in
Earth orbit include albedo and Earth IR, not just direct solar. Note that most
coatings degrade toward higher alpha over mission life -- use end-of-life
properties for hot cases and beginning-of-life for cold cases.

Always analyse both a hot case and a cold case. Follow the thermal answer through
to its structural consequence: differential expansion, joint preload change,
bond line stress, and fatigue from repeated cycling.""",
    },
    "composites": {
        "label": "COMPOSITES",
        "blurb": "Laminates, layup, failure criteria, bonded joints",
        "sections": ("composites", "stress", "space"),
        "starters": [
            "Propose a layup for this panel and justify the ply angles.",
            "Which failure criterion applies here, and what is the margin?",
            "Design a bonded or bolted joint into this laminate.",
            "How should this composite structure handle its thermal environment?",
        ],
        "prompt": """DISCIPLINE FOCUS: COMPOSITE MATERIALS AND LAMINATE THEORY.

Composites are not isotropic and cannot be checked with a single allowable.
Work in laminate terms: define the stacking sequence, then reason through
classical lamination theory (A, B, D matrices) to get laminate stiffness, then
transform back to ply-level stresses in material axes before applying a failure
criterion.

State and justify the criterion used -- maximum stress/strain for
non-interactive screening, Tsai-Hill or Tsai-Wu for combined loading, and note
that Tsai-Wu distinguishes tension from compression while Tsai-Hill does not.
Distinguish first-ply failure from last-ply failure and say which governs.

Enforce the layup rules and explain when they are being broken deliberately:
symmetric to avoid extension-bending coupling, balanced to avoid
extension-shear coupling, no more than about four adjacent same-angle plies, at
least ~10% of plies in each principal direction, and 45-degree plies at the
surface for impact and handling.

Treat the matrix-dominated properties as the weak link: transverse tension,
interlaminar shear, and out-of-plane loading. Composites have essentially no
through-thickness strength, so flag any design that puts peel or through-
thickness tension into a laminate or a bondline.

Address damage tolerance explicitly -- barely visible impact damage, free-edge
delamination, and hole/bearing behaviour in bolted joints -- and note that
knockdown factors for environment (hot/wet) and damage are normal practice.""",
    },
    "vibrations": {
        "label": "VIBRATIONS",
        "blurb": "Modes, random vibration, shock, launch environments",
        "sections": ("metals", "stress", "vibration", "space"),
        "starters": [
            "Estimate the first natural frequency of this structure.",
            "Run a Miles' equation check for this random vibration environment.",
            "Will this design survive the launch vibration spec?",
            "How do I raise the first mode of this bracket?",
        ],
        "prompt": """DISCIPLINE FOCUS: VIBRATIONS AND DYNAMIC ENVIRONMENTS.

Begin with the first natural frequency and say what it is driven by -- stiffness
distribution and mass placement, not strength. Most fixes are geometry and load
path changes, not thicker material.

Keep the environments separate and do not substitute one for another: sine
sweep, random vibration (PSD, g^2/Hz), acoustic, and pyro/mechanical shock (SRS)
are distinct qualification cases with distinct failure mechanisms.

For random vibration, use Miles' equation as a first-cut single-degree-of-freedom
estimate, state the assumed amplification factor Q and why, and treat the result
as a 1-sigma value -- design to 3-sigma. Say explicitly that Miles' equation is
an approximation valid for a narrow-band, single-mode response, and that closely
spaced modes or significant participation from several modes require an FEM
random response run instead.

Check both peak stress and fatigue life: random vibration failures are usually
high-cycle fatigue, not one overload event. Sum damage across the qualification
and acceptance test sequence, not just flight.

Watch for coupling: an appendage whose natural frequency sits near a primary
structure mode will amplify badly. Note the frequency separation rule of thumb
(commonly a factor of ~2 between coupled subsystems) and remember that isolation
only attenuates above sqrt(2) times the isolator frequency and amplifies below it.""",
    },
    "gdt": {
        "label": "GD&T / TOLERANCING",
        "blurb": "Datums, feature control frames, stackups",
        "sections": ("gdt", "fits"),
        "starters": [
            "What GD&T callouts belong on this drawing?",
            "Set up a datum reference frame for this part.",
            "Run a tolerance stackup on this assembly.",
            "Is this tolerance achievable, and what will it cost?",
        ],
        "prompt": """DISCIPLINE FOCUS: GD&T AND TOLERANCING (ASME Y14.5).

Start from function. Every tolerance should trace to something the part has to
do -- fit, seal, align, carry load, or be assembled -- and a tolerance with no
functional justification is pure cost.

Establish the datum reference frame first and justify it from how the part is
located in the assembly and how it will be fixtured for inspection. Datum
precedence order changes the meaning of everything downstream; state it and say
what each datum constrains.

Prefer position and profile over the legacy controls; note that concentricity
and symmetry are deprecated in Y14.5-2018 and should generally be replaced.
Apply MMC where the requirement is assembly clearance so the part earns bonus
tolerance, and RFS where the requirement is alignment or balance.

For stackups, state the method: worst case sums tolerances arithmetically and
guarantees assembly; RSS is statistically based, gives a looser and cheaper
result, and is only legitimate for independent, in-control processes with
adequate sample size. Show the loop diagram and identify which contributor
dominates -- that is where tolerance money should be spent.

Sanity-check achievability against normal process capability before specifying,
and say when a tolerance will force a secondary operation such as grinding,
reaming, or match-drilling at assembly.""",
    },
    "fasteners": {
        "label": "FASTENERS / JOINTS",
        "blurb": "Preload, torque, joint analysis, locking",
        "sections": ("metals", "fasteners", "stress", "fatigue", "space"),
        "starters": [
            "What fastener size, grade, and torque should this joint use?",
            "Check this bolted joint for separation and slip.",
            "How much thread engagement do I need in this material?",
            "What locking method is appropriate here?",
        ],
        "prompt": """DISCIPLINE FOCUS: FASTENERS AND BOLTED JOINTS.

Analyse the joint, not just the bolt. A bolted joint is a preloaded spring
system: establish preload first, then the stiffness ratio between bolt and
clamped members, then how much of the external load the bolt actually sees.

Check all of these, and say which governs: separation (gapping) under limit
load, slip if the joint carries shear by friction, bolt tension and shear
(with interaction when combined), thread stripping in the weaker member,
bearing and tear-out in the joined parts, and bolt fatigue under cyclic load.

Preload is the whole game. State the target preload as a fraction of proof or
yield, the torque that produces it, the assumed nut factor K, and the resulting
uncertainty -- torque control is only about +/-25-35% accurate on preload. Note
what erodes preload over life: embedment, gasket creep, thermal cycling with
CTE mismatch, and vibration loosening.

Size thread engagement to the weaker material and specify inserts (helicoil,
keensert) in aluminium and plastics, especially for joints that will be
disassembled.

Specify a positive locking feature and say why it suits the environment: split
lock washers are largely ineffective under vibration, nylon inserts are
temperature limited, and spaceflight joints normally require locking that does
not depend on friction alone. Give a specific fastener callout, not just a size --
material, finish, head style, and standard.""",
    },
    "manufacturing": {
        "label": "MANUFACTURING / DFM",
        "blurb": "Process selection, machinability, cost drivers",
        "sections": ("metals", "polymers", "manufacturing", "fits"),
        "starters": [
            "Review this part for manufacturability.",
            "Which process should make this part at this quantity?",
            "How do I make this part cheaper without hurting function?",
            "What tolerances and finishes are realistic for this process?",
        ],
        "prompt": """DISCIPLINE FOCUS: MANUFACTURING AND DESIGN FOR MANUFACTURABILITY.

Tie every recommendation to a process and a quantity. The right design for five
units is not the right design for five thousand: machining and additive win at
low volume, casting and moulding win at high volume once tooling amortises.

Work through the specific constraints of the chosen process -- for machining,
tool access and reach, minimum internal corner radii set by cutter size, depth-
to-diameter limits, setup count and the tolerance penalty of every refixture,
and workholding for thin or flexible parts. For sheet metal, bend radii, flange
lengths, hole-to-bend distances, and grain direction. For moulding, uniform wall
thickness, draft, and sink. For additive, overhang angle, support removal
access, anisotropy, and required post-processing.

Name the cost drivers in order and say which one this part is paying for:
tolerance tightness, setup count, material removal volume, surface finish
callouts, and inspection burden. A single unnecessary tight tolerance or an
unreachable internal feature often costs more than the entire rest of the part.

Give concrete alternatives rather than only criticism: a specific radius to add,
a feature to move to a second face, a tolerance to open up, a wall to thicken.

Flag anything that will need a first-article inspection, special fixturing, or a
process qualification, since those drive schedule as much as cost.""",
    },
}

# Order shown in the UI.
DOMAIN_ORDER = (
    "statics",
    "materials",
    "thermal",
    "composites",
    "vibrations",
    "gdt",
    "fasteners",
    "manufacturing",
)


def is_valid(domain: str | None) -> bool:
    return domain in DOMAINS


def get_prompt(domain: str | None) -> str:
    if not is_valid(domain):
        return ""
    return DOMAINS[domain]["prompt"]


def get_sections(domain: str | None) -> tuple[str, ...] | None:
    """Reference sections this discipline needs, or None for everything."""
    if not is_valid(domain):
        return None
    return DOMAINS[domain]["sections"]


def catalog() -> list[dict]:
    return [
        {
            "id": key,
            "label": DOMAINS[key]["label"],
            "blurb": DOMAINS[key]["blurb"],
            "starters": DOMAINS[key]["starters"],
        }
        for key in DOMAIN_ORDER
    ]
