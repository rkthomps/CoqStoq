from coqstoq.eval_thms import Project, Split

TEST_SPLIT = Split("test-repos", "test-theorems")
VAL_SPLIT = Split("val-repos", "val-theorems")
CUTOFF_SPLIT = Split("cutoff-repos", "cutoff-theorems")

COMPCERT = Project(
    "compcert",
    TEST_SPLIT,
    "6019bc41556473897155259e3d15c5d689185569",
    [
        "-R",
        "lib",
        "compcert.lib",
        "-R",
        "common",
        "compcert.common",
        "-R",
        "x86_64",
        "compcert.x86_64",
        "-R",
        "x86",
        "compcert.x86",
        "-R",
        "backend",
        "compcert.backend",
        "-R",
        "cfrontend",
        "compcert.cfrontend",
        "-R",
        "driver",
        "compcert.driver",
        "-R",
        "export",
        "compcert.export",
        "-R",
        "cparser",
        "compcert.cparser",
        "-R",
        "flocq",
        "Flocq",
        "-R",
        "MenhirLib",
        "MenhirLib",
    ],
)

EXTLIB = Project(
    "ext-lib",
    TEST_SPLIT,
    "00d3f4e2a260c7c23d2c0b9cbc69516f8be4ac92",
    ["-Q", "theories", "ExtLib"],
)

FOURCOLOR = Project(
    "fourcolor",
    TEST_SPLIT,
    "43719c0fb5fb6cb0c8fc1c2db09efc632c23df90",
    ["-R", "theories", "fourcolor"],
)

MATHCLASSES = Project(
    "math-classes",
    TEST_SPLIT,
    "6ad1db9fbd646f8daf1568afef230a76a9f58643",
    ["-R", ".", "MathClasses"],
)

REGLANG = Project(
    "reglang",
    TEST_SPLIT,
    "db8be63ec40349e529b6a57c8bcee1acb3f90ceb",
    ["-Q", "theories", "RegLang"],
)

BUCHBERGER = Project(
    "buchberger",
    TEST_SPLIT,
    "55ee2e82a05904a7dfb060e558044284abe9c9f5",
    ["-Q", "theories", "Buchberger"],
)

HOARETUT = Project(
    "hoare-tut",
    TEST_SPLIT,
    "66dfb255c9e8bb49269d83b3577b285288f39928",
    ["-R", ".", "HoareTut"],
)

ZORNSLEMMA = Project(
    "zorns-lemma",
    TEST_SPLIT,
    "aaf46b0c5f7857ce9211cbaaf36f184ca810e0e8",
    ["-R", ".", "ZornsLemma"],
)

HUFFMAN = Project(
    "huffman",
    TEST_SPLIT,
    "03d40bd01f2bbccf774e369a3d3feaa2b2a5524a",
    ["-Q", "theories", "Huffman"],
)

POLTAC = Project(
    "poltac",
    TEST_SPLIT,
    "90c42be344fd778261fd84b065809b2c81938c49",
    ["-R", ".", "PolTac"],
)

DBLIB = Project(
    "dblib",
    TEST_SPLIT,
    "25469872c0ba99b046f7e5b8608205eeea5ac077",
    ["-Q", "src", "Dblib"],
)

ZFC = Project(
    "zfc",
    TEST_SPLIT,
    "ede7126560844c381c2b021003a8dbcb0668ecad",
    ["-R", ".", "ZFC"],
)

TEST_PROJECTS = [
    COMPCERT,
    EXTLIB,
    FOURCOLOR,
    MATHCLASSES,
    REGLANG,
    BUCHBERGER,
    HOARETUT,
    ZORNSLEMMA,
    HUFFMAN,
    POLTAC,
    DBLIB,
    ZFC,
]


SUDOKU = Project(
    "sudoku",
    VAL_SPLIT,
    "fce3ced21fe5f66d593cf817f70508ba914e8373",
    ["-R", "theories", "Sudoku"],
)

BERTRAND = Project(
    "bertrand",
    VAL_SPLIT,
    "033b1a8f1a9c121855b6b78cd55154d3c09e1c23",
    ["-Q", "theories", "Bertrand"],
)

GRAPH_THEORY = Project(
    "graph-theory",
    VAL_SPLIT,
    "4bc29600fd8df75a34f6c0e9c18589c597742a60",
    ["-Q", "theories", "GraphTheory"],
)

STALMARCK = Project(
    "stalmarck",
    VAL_SPLIT,
    "4643e9507e7f03d485fc63410f7f500984d5be8b",
    ["-Q", "theories", "Stalmarck"],
)

QARITH_STERN_BROCOT = Project(
    "qarith-stern-brocot",
    VAL_SPLIT,
    "d3807d3e76a3100e85ba24ef3fe0520f10a7c928",
    ["-R", "theories", "QArithSternBrocot"],
)

COQEAL = Project(
    "coqeal",
    VAL_SPLIT,
    "fb2ecaf4cf99d91351e2a18418d14bea8f24ca60",
    ["-R", ".", "CoqEAL"],
)

VAL_PROJECTS = [
    SUDOKU,
    BERTRAND,
    GRAPH_THEORY,
    STALMARCK,
    QARITH_STERN_BROCOT,
    COQEAL,
]

BB5 = Project(
    "bb5",
    CUTOFF_SPLIT,
    "632ba68b03adb27f4f6faaa76b83db934d5ecbba",
    ["-Q", ".", "BusyCoq"],
)

PNVROCQLIB = Project(
    "pnvrocqlib",
    CUTOFF_SPLIT,
    "f621247710cd561539dbdbf5c95d56c29ae545c8",
    ["-Q", "theories", "PnV"],
)

CUTOFF_PROJECTS = [PNVROCQLIB, BB5]

PREDEFINED_PROJECTS = TEST_PROJECTS + VAL_PROJECTS + CUTOFF_PROJECTS
