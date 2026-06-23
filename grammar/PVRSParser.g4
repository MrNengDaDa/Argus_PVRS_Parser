parser grammar PVRSParser;

options { tokenVocab = PVRSLexer; }

// ============================================================
// 1. Entry point
// ============================================================
pvrFile : statement* EOF ;

// ============================================================
// 2. Statement types
// ============================================================
statement : environment_stmt | derived_layer_def | op_statement | rule_statement | groupRule ;
derived_layer_def : layerRef ASSIGN op_statement ;
rule_statement : RULE name LBRACE rule_body RBRACE ;
rule_body : (derived_layer_def | op_statement)*;
environment_stmt
    : drcOutputRuleText | drcOutputCellName | labelLevel
    | precisionStmt | layerStmt | layerMapStmt
    | incrementalConnect | virtualConnect
    | labelLayer | attachStmt | connectStmt
    | layoutInput | layoutDeviceLayer
    | drcResultDb | drcResultPrecision
    | drcMaxResult | drcMaxVertex | drcSummary | guiPriority
    | ercResultDb | ercMaxResult | ercSummary | ercOutputCellName
    | lvsPower | lvsGround
    | drcRuleMap
    | varStmt
    | defineFun
    ;

op_statement
    : geomInteract | geomOr | geomAnd | geomXor | geomCut
    | geomWithEdge | geomAdjacent | geomWithWidth | geomWithLabel
    | geomEnclose | geomDonut | geomInside | geomOutside | geomRectangle
    | geomHoles | geomEdgeToRect | geomOrthSize
    | geomSize | geomGetBoundaries | geomArea | geomNot | encRect | geomTransferNetid
    | edgeAngle | edgeLength | edgeInside | edgeCoincident | edgeConvexPoint | edgeAdjacent | edgeOr
    | dimensionalCheck | encCheck | extensionCheck | widthCheck | overlapCheck
    | checkDensity | copyOp | geomGetBoundary | checkNar
    | dfmBuildProperty | dfmCopy | dfmResult | dfmBuildPropertySelectAssistant | dfmCheckSpace | dfmOrEdge
    | geomNet | geomGetCellBoundary | geomWithAdjacent
    | geomGetLayoutBoundary | geomMerge | geomFlatten
    | callFun
    ;

// ============================================================
// 3. GEOM_INTERACT
// ============================================================
geomInteract
    : TILDE? GEOM_INTERACT LPAREN op_layer op_layer constraint? COUNT_BY_NET? (EVEN | ODD)? (POINT_TOUCH | ONLY_POINT_TOUCH)? RPAREN ;

// ============================================================
// 4. GEOM_OR / OR
// ============================================================
geomOr : (GEOM_OR | OR) LPAREN op_layer (op_layer)* RPAREN ;

// ============================================================
// 5. GEOM_AND / AND
// ============================================================
geomAnd
    : (GEOM_AND | AND) LPAREN op_layer op_layer (SAME_NET | DIFF_NET)? CELL_LEVEL? RPAREN
    | (GEOM_AND | AND) LPAREN op_layer constraint CELL_LEVEL? RPAREN ;

// ============================================================
// 6. GEOM_CUT
// ============================================================
geomCut
    : TILDE? GEOM_CUT LPAREN op_layer op_layer constraint? COUNT_BY_NET? (EVEN | ODD)? RPAREN ;

// ============================================================
// 7. GEOM_WITH_EDGE
// ============================================================
geomWithEdge
    : TILDE? GEOM_WITH_EDGE LPAREN op_layer op_layer constraint? RPAREN ;

// ============================================================
// 8. GEOM_ADJACENT
// ============================================================
geomAdjacent
    : TILDE? GEOM_ADJACENT LPAREN op_layer op_layer constraint? COUNT_BY_NET? (EVEN | ODD)? RPAREN ;

// ============================================================
// 9. GEOM_WITH_WIDTH
// ============================================================
geomWithWidth
    : TILDE? GEOM_WITH_WIDTH LPAREN op_layer constraint RPAREN ;

geomWithLabel
    : TILDE? GEOM_WITH_LABEL LPAREN op_layer name op_layer? TOP_CELL? CASE_SENSITIVE? RPAREN ;

// ============================================================
// 10. GEOM_ENCLOSE
// ============================================================
geomEnclose
    : TILDE? GEOM_ENCLOSE LPAREN op_layer op_layer constraint? COUNT_BY_NET? (EVEN | ODD)? RPAREN ;

geomInside
    : TILDE? GEOM_INSIDE LPAREN op_layer op_layer RPAREN ;

geomOutside
    : TILDE? GEOM_OUTSIDE LPAREN op_layer op_layer RPAREN ;

// ============================================================
// 11. GEOM_DONUT
// ============================================================
geomDonut : TILDE? GEOM_DONUT LPAREN op_layer constraint? RPAREN ;

// ============================================================
// 12. GEOM_RECTANGLE
// ============================================================
geomRectangle
    : TILDE? GEOM_RECTANGLE LPAREN op_layer constraint? (BY constraint)? (RATIO constraint)? rectOption? RPAREN ;
rectOption : ORTHOGONAL FIXED? | BY_BOUNDARIES ;

// ============================================================
// 12b. ENC_RECT  (PDF p.331)
// ============================================================
encRect
    : ENC_RECT LPAREN
        op_layer op_layer
        encRectOption*
        rectangleRule+
      RPAREN ;

encRectOption
    : ADJACENT constraint?
    | POINT_TOUCH | ONLY_POINT_TOUCH
    | OUTSIDE_ALSO
    | INSIDE_ALSO
    | ONLY_ORTHOGONAL
    ;

rectangleRule
    : (CORRECT | INCORRECT) (expr metric?)+ ;

metric : OPPOSITE | SQUARE | OPPOSITE_EXTENDED expr? | EXTENDED_OPPOSITE expr? ;

// ============================================================
// 13. GEOM_HOLES
// ============================================================
geomHoles : GEOM_HOLES LPAREN op_layer constraint? holeOption* RPAREN ;
holeOption : INNER_MOST | HOLLOW | POINT_TOUCH | ONLY_POINT_TOUCH;

// ============================================================
// 14. GEOM_EDGE_TO_RECT
// ============================================================
geomEdgeToRect
    : GEOM_EDGE_TO_RECT LPAREN op_layer expansionOption extendOption? FILL_CORNER? CELL_LEVEL? RPAREN ;
expansionOption
    : INSIDE expr | INSIDE_BY_FACTOR expr
    | OUTSIDE expr | OUTSIDE_BY_FACTOR expr
    | BOTH_SIDE expr | BOTH_SIDE_BY_FACTOR expr ;
extendOption : EXTEND expr | EXTEND_BY_FACTOR expr ;

// ============================================================
// 15. GEOM_ORTH_SIZE
// ============================================================
geomOrthSize : GEOM_ORTH_SIZE LPAREN op_layer orthOption* IN_ORDER? RPAREN ;
orthOption
    : RIGHT expr | TOP expr
    | LEFT expr | BOTTOM expr ;

// ============================================================
// 16. GEOM_SIZE
// ============================================================
geomSize
    : GEOM_SIZE LPAREN op_layer BY expr sizeOption* RPAREN ;
sizeOption
    : OUTPUT_OVERLAP_REGION | OUT_IN | IN_OUT
    | INSIDE_OF_LAYER op_layer (DELTA expr)?
    | OUTSIDE_OF_LAYER op_layer (DELTA expr)?
    | CLIP expr
    | CLIP_CORNER expr
    | CELL_LEVEL ;

// ============================================================
// 17. GEOM_GET_BOUNDARIES
// ============================================================
geomGetBoundaries : GEOM_GET_BOUNDARIES LPAREN op_layer getBoundaryOption* RPAREN ;
getBoundaryOption : OUTPUT_CENTER expr? | OUTPUT_SQUARE | INSIDE_OF_LAYER op_layer ;

// ============================================================
// 18. GEOM_AREA
// ============================================================
geomArea : TILDE? GEOM_AREA LPAREN op_layer constraint RPAREN ;

// ============================================================
// 19. EDGE_ANGLE
// ============================================================
edgeAngle : TILDE? EDGE_ANGLE LPAREN op_layer constraint? CELL_LEVEL? RPAREN ;
edgeLength : TILDE? EDGE_LENGTH LPAREN op_layer constraint? CELL_LEVEL? RPAREN ;

// ============================================================
// 20. EDGE_INSIDE
// ============================================================
edgeInside : TILDE? EDGE_INSIDE LPAREN op_layer op_layer RPAREN ;

// ============================================================
// 21. EDGE_COINCIDENT
// ============================================================
edgeAdjacent : TILDE? EDGE_ADJACENT LPAREN (OUTSIDE | INSIDE | BOTH_SIDE) op_layer op_layer (POINT | ONLY_POINT)? RPAREN ;
edgeCoincident : TILDE? EDGE_COINCIDENT LPAREN (OUTSIDE | INSIDE | BOTH_SIDE) op_layer op_layer RPAREN ;

// ============================================================
// 21a. EDGE_OR
// ============================================================
edgeOr : EDGE_OR LPAREN op_layer op_layer RPAREN ;

// ============================================================
// 22. EDGE_CONVEX_POINT
// ============================================================
edgeConvexPoint
    : EDGE_CONVEX_POINT LPAREN
        op_layer edgeConvexPointSpec* (WITH_EDGE_LENGTH constraint)? RPAREN
    | EDGE_CONVEX_POINT LPAREN
        op_layer constraint (WITH_EDGE_LENGTH constraint)? RPAREN ;

edgeConvexPointSpec
    : (ADJACENT_EDGE_ANGLE1 | ADJACENT_EDGE_ANGLE2 | ADJACENT_EDGE_LENGTH1 | ADJACENT_EDGE_LENGTH2) constraint
    ;

// ============================================================
// 23. GEOM_NOT / NOT
// ============================================================
geomNot : (GEOM_NOT | NOT) LPAREN op_layer op_layer CELL_LEVEL? RPAREN ;
geomTransferNetid : GEOM_TRANSFER_NETID LPAREN op_layer BY op_layer INCLUDE_ADJACENT? RPAREN ;
geomXor : (GEOM_XOR | XOR) LPAREN op_layer op_layer CELL_LEVEL? RPAREN
        | (GEOM_XOR | XOR) LPAREN op_layer CELL_LEVEL? RPAREN ;

// ============================================================
// 24. Dimensional checks (EXT/SPACE/ENC/EXTENSION/WIDTH/OVERLAP/INT)
// ============================================================

// EXT/SPACE/INT: one-layer or two-layer
dimensionalCheck
    : (EXT | SPACE | INT) LPAREN op_layer op_layer constraint intOption* RPAREN
    | (EXT | SPACE | INT) LPAREN op_layer constraint intOption* RPAREN ;

// ENC/EXTENSION/OVERLAP: two-layer only
encCheck
    : ENC LPAREN op_layer op_layer constraint intOption* RPAREN ;
extensionCheck
    : EXTENSION LPAREN op_layer op_layer constraint intOption* RPAREN ;
overlapCheck
    : OVERLAP LPAREN op_layer op_layer constraint intOption* RPAREN ;

// WIDTH: one-layer (with multiple layers via op_layer+)
widthCheck
    : WIDTH LPAREN op_layer+ constraint intOption* RPAREN ;

// --- Shared option groups for all dimensional checks ---

intOption
    : measurementMetric
    | orientationOption
    | measurementContain
    | connectivityOption
    | appositionOption
    | angleOption
    | cornerOption
    | intersectionOption
    | regionOption
    | INSIDE_ALSO | OUTSIDE_ALSO
    | COUNT expr
    | INT_LIT | FLOAT
    ;

measurementMetric
    : OPPOSITE | SQUARE | SQUARE_ORTHOGONAL | EUCLIDEAN
    | EXTENDED_OPPOSITE expr?
    | OPP_SYM | OPP_FSYM
    | OPP_SYM_EXTENDED expr?
    | OPP_FSYM_EXTENDED expr?
    | OPPOSITE1 | OPPOSITE2
    | OPPOSITE_EXTENDED1 expr?
    | OPPOSITE_EXTENDED2 expr?
    ;

orientationOption
    : ACUTE_ONLY | ACUTE_ALSO | NOT_ACUTE
    | PARALLEL_ONLY | PARALLEL_ALSO | NOT_PARALLEL
    | PERPENDICULAR_ONLY | PERPENDICULAR_ALSO | NOT_PERPENDICULAR
    | OBTUSE_ONLY | OBTUSE_ALSO | NOT_OBTUSE
    ;

measurementContain
    : ALL_EDGE | COINCIDENT_EDGE_ALSO
    | SHIELDED_LEVEL expr?
    ;

connectivityOption
    : SAME_NET | DIFF_NET | SAME_POLYGON | DIFF_POLYGON
    ;

appositionOption
    : APPOSITION constraint?
    | NO_APPOSITION
    ;

angleOption
    : ANGLED_EDGE constraint?
    ;

cornerOption
    : CORNER_CORNER | CORNER_EDGE | ALL_CORNER | NOT_CORNER
    ;

intersectionOption
    : INTERSECTING_ONLY | OVERLAPPED | POINT_TOUCH | ONLY_POINT_TOUCH
    | ADJACENT constraint?
    ;

regionOption
    : REGION | REGION_BOUNDARIES
    | REGION_CENTERLINE expr?
    ;

// ============================================================
// 25. CHECK_DENSITY
// ============================================================
checkDensity : CHECK_DENSITY LPAREN op_layer (op_layer)* constraint densityOption* RPAREN ;
densityOption
    : BY_WINDOW expr expr?
    | DELTA expr expr?
    | BOUNDARY_TRUNCATE | BOUNDARY_BACKUP | BOUNDARY_IGNORE | BOUNDARY_REPEAT
    | INSIDE_OF_BOUNDARY
    | INSIDE_OF_REGION expr expr expr expr
    | INSIDE_OF_LAYER op_layer (IN_BOUNDARIES | IN_POLYGON | (IN_BOUNDARIES_CENTER expr))?
    | CHECK_GRADIENT constraint (RELATIVE_RATIO | ABSOLUTE_VALUE)? (CORNER_ALSO expr?)?
    | CHECK_SEPARATE_GRADIENT constraint (RELATIVE_RATIO | ABSOLUTE_VALUE)?
    | OUTPUT_CENTER expr
    | OUTPUT_LOG (ONLY_OUTPUT_LOG)? ID
    | RESULT_DB (ONLY_RESULT_DB)? ID (MAG expr)?
    | INT_LIT | FLOAT | ID ;

// ============================================================
// 26. COPY
// ============================================================
copyOp : COPY LPAREN op_layer RPAREN ;
geomGetBoundary : GEOM_GET_BOUNDARY LPAREN op_layer? RPAREN ;

// ============================================================
// 27b. CHECK_NAR
// ============================================================
checkNar
    : CHECK_NAR LPAREN
        op_layer+ DIVIDE? op_layer* checkNarConstraint
        checkNarOption*
      RPAREN ;

checkNarConstraint
    : (LBRACK expr RBRACK)? constraint
    | constraint (LBRACK expr RBRACK)?
    ;

checkNarOption
    : INSIDE_OF_LAYER op_layer SAME_NET?
    | INCREMENTAL op_layer*
    | (RESULT_DB | ONLY_RESULT_DB) ID (MAG expr)? OUTPUT_BY_LAYER? resultDbLayer*
    ;

resultDbLayer : op_layer (MAX expr)? ;

// ============================================================
// 27c. DFM_BUILD_PROPERTY
// ============================================================
dfmBuildProperty
    : DFM_BUILD_PROPERTY LPAREN
        op_layer op_layer*
        dfmClusterOption?
        dfmGlobalOption*
        dfmPropertyDef*
      RPAREN ;

dfmClusterOption
    : CLIP
    | OVERLAPPED dfmOverlapOption*
    | NODAL dfmClusterMode? NOPUSH?
    ;

dfmOverlapOption : ADJACENT | POINT_TOUCH | ONLY_POINT_TOUCH | dfmClusterMode | NOPUSH | REGION ;
dfmClusterMode : MULTI_CLUSTER | SINGLE_CLUSTER ;
dfmGlobalOption : NO_GLOBALXY | GLOBALXY | DBU ;

dfmPropertyDef
    : LBRACK funcName ASSIGN expr RBRACK (BANG? constraint)?
    ;

// ============================================================
// 27c. DFM_BUILD_PROPERTY_SELECT_ASSISTANT
// ============================================================
dfmBuildPropertySelectAssistant
    : DFM_BUILD_PROPERTY_SELECT_ASSISTANT LPAREN
        op_layer op_layer+
        dfmClusterOption?
        dfmPropertyDef*
        SELECT op_layer
        SINGLE_CLUSTER?
        dfmPropertyDef*
      RPAREN
    ;

// ============================================================
// 27c2. DFM_CHECK_SPACE
// ============================================================
dfmCheckSpace
    : DFM_CHECK_SPACE LPAREN
        dfmCheckSpaceCore
        dfmCheckSpaceOption*
      RPAREN
    ;

dfmCheckSpaceCore
    : op_layer op_layer? constraint dfmCheckSpaceMeasure
    | dfmCheckSpaceMeasure op_layer op_layer? constraint
    ;

dfmCheckSpaceMeasure
    : BY_EXT | BY_INT | BY_ENC | BY_ALL
    ;

dfmCheckSpaceOption
    : X_DIRECTION
    | Y_DIRECTION
    | SHIELD_LEVEL constraint
    | SHIELD_LAYER op_layer
    | CHECK_ALL
    | SAME_NET
    | DIFF_NET
    | DELTA expr
    ;

// ============================================================
// 27c3. DFM_OR_EDGE
// ============================================================
dfmOrEdge
    : DFM_OR_EDGE LPAREN op_layer op_layer+ RPAREN
    ;

// ============================================================
// 27d. GEOM_NET
// ============================================================
geomNet
    : TILDE? GEOM_NET LPAREN BY_AREA op_layer constraint RPAREN
    | TILDE? GEOM_NET LPAREN BY_LAYER op_layer layerRef+ RPAREN
    ;

// ============================================================
// 27e. GEOM_GET_CELL_BOUNDARY
// ============================================================
geomGetCellBoundary
    : GEOM_GET_CELL_BOUNDARY LPAREN
        layerRef+
        ((ORIGINAL_LAYER | MAPPED_LAYER) USED_LAYER?)?
        (PATTERN_MATCH GOLDEN?)?
      RPAREN ;

// ============================================================
// 27f. DFM_COPY
// ============================================================
dfmCopy
    : DFM_COPY LPAREN op_layer+ dfmCopyOption? (CELL_GROUP ID)? RPAREN ;

dfmCopyOption
    : REGION | UNMERGED_REGION | EDGE | MIDDLE_LINE
    | CONNECTING_LINE | CONNECTING_MIDPOINT
    | EDGE_COLLECTION LAYER_ID?
    | UNMERGED_EDGE
    ;

// ============================================================
// 27g. DFM_RESULT
// ============================================================
dfmResult
    : DFM_RESULT LPAREN op_layer layerRef dfmResultOption* RPAREN ;

dfmResultOption
    : FIRST_NODE | ALL_NODE | OTHER_NODE
    | FLATTEN_INJECTION
    | TOP_CELL
    | IGNORE_EMPTY
    | ALL_CELL
    | NOT_KEEP_INJECTED_CELL
    | OUTPUT_BOUNDARY
    | MAX_RESULT (ALL | expr)
    | RULE_NAME layerRef
    | COMMENT STRING
    ;

// ============================================================
// 27h. GEOM_WITH_ADJACENT
// ============================================================
geomWithAdjacent
    : TILDE? GEOM_WITH_ADJACENT LPAREN
        op_layer op_layer? constraint DISTANCE constraint
        geomWithAdjacentOption*
      RPAREN ;

geomWithAdjacentOption
    : SQUARE
    | FROM_CENTER (OCTAGONAL_RECT | ORTHOGONAL_RECT)?
    | INSIDE_OF_LAYER op_layer
    | SAME_NET | DIFF_NET
    ;

// ============================================================
// 27. GEOM_GET_LAYOUT_BOUNDARY
// ============================================================
geomGetLayoutBoundary
    : GEOM_GET_LAYOUT_BOUNDARY LPAREN
        (ORIGINAL_LAYER | layerRef+)?
        (IGNORE_LAYER layerRef+)?
      RPAREN
    ;

// ============================================================
// 28. GEOM_MERGE
// ============================================================
geomMerge
    : GEOM_MERGE LPAREN op_layer (BY expr)? RPAREN
    ;

// ============================================================
// 28b. GEOM_FLATTEN
// ============================================================
geomFlatten
    : GEOM_FLATTEN LPAREN op_layer RPAREN
    ;

// ============================================================
// 29. Environment statements
// ============================================================
drcOutputRuleText : DRC_OUTPUT_RULE_TEXT LPAREN (COMMENT | ALL | NONE) RPAREN ;
drcOutputCellName : DRC_OUTPUT_CELL_NAME LPAREN (NO | YES cellNameOption*) RPAREN ;
cellNameOption : CELL_COORDINATE | TRANSFORM_TO_TOP | ALL ;
labelLevel : LABEL_LEVEL LPAREN (TEXT | PORT) (TOP_CELL | ALL | INT_LIT) RPAREN ;
precisionStmt : PRECISION LPAREN (expr | expr expr) RPAREN ;
layerStmt : LAYER LPAREN layerRef layerRef+ RPAREN ;
layerMapStmt : LAYER_MAP LPAREN (layerRef | constraint) (DATATYPE (layerRef | constraint) layerRef | TEXTTYPE EQ? layerRef layerRef layerRef?) RPAREN ;
incrementalConnect : INCREMENTAL_CONNECT LPAREN (NO | YES) RPAREN ;
virtualConnect : VIRTUAL_CONNECT LPAREN virtualConnectBody RPAREN ;
virtualConnectBody
    : BLACK_BOX_COLON (NO | YES)
    | BLACK_BOX_NAME layerRef+
    | COLON (NO | YES)
    | INCREMENTAL_CONNECT (NO | YES)
    | LEVEL (TOP_CELL | ALL)
    | NAME layerRef+
    | REPORT_WARNING (NO | YES)
    | REPORT_MAX (ALL | INT_LIT)
    | SEMICOLON (YES | NO)
    ;
labelLayer : LABEL_LAYER LPAREN (PORT_POLYGON | TEXT | PORT) layerRef+ RPAREN ;
attachStmt : ATTACH LPAREN op_layer op_layer RPAREN ;
connectStmt : CONNECT LPAREN op_layer op_layer* ((BY | WITH) op_layer)? RPAREN ;

// ============================================================
// 26. LAYOUT_INPUT
// ============================================================
layoutInput
    : LAYOUT_INPUT LPAREN FORMAT formatType RPAREN
    | LAYOUT_INPUT LPAREN PATH layoutPathSpec+ RPAREN
    | LAYOUT_INPUT LPAREN TOP_CELL name RPAREN
    ;

layoutPathSpec
    : (ID | STRING | STDIN) layoutPathOption*
    ;

layoutPathOption
    : MAGNIFY (expr | AUTO)
    | PRECISION expr
    | PRECISION LBRACE expr expr RBRACE
    ;

layoutDeviceLayer
    : LAYOUT_DEVICE_LAYER LPAREN layerRef+ RPAREN
    ;

lvsPower
    : LVS_POWER LPAREN name+ RPAREN
    ;

lvsGround
    : LVS_GROUND LPAREN name+ RPAREN
    ;

varStmt
    : VAR LPAREN ID atom+ RPAREN
    ;

defineFun
    : DEFINE_FUN ID ID* LBRACE defineFunBody RBRACE
    ;

defineFunBody
    : (~RBRACE)*
    ;

callFun
    : CALL_FUN LPAREN ID atom* RPAREN
    ;

// ============================================================
// 27. DRC_RESULT, DRC_MAX_*, DRC_SUMMARY, GUI_PRIORITY
// ============================================================
drcResultDb
    : DRC_RESULT LPAREN DB name drcResultDbOption* RPAREN
    ;

drcResultDbOption
    : TEXT_FORMAT
    | formatType
    | WITH_PREFIX name
    | WITH_INJECTED_PREFIX name
    | WITH_APPEND name
    | MERGED
    | KEEP_INJECTED_CELL
    | USER_CELL
    | TOP_CELL
    | NOCBLOCK
    ;

drcResultPrecision
    : DRC_RESULT LPAREN PRECISION expr RPAREN
    | DRC_RESULT LPAREN PRECISION expr expr RPAREN
    ;

drcMaxResult
    : DRC_MAX_RESULT LPAREN (expr | ALL) RPAREN
    ;

drcMaxVertex
    : DRC_MAX_VERTEX LPAREN (expr | ALL) RPAREN
    ;

drcSummary
    : DRC_SUMMARY LPAREN name (OVERWRITE | APPEND)? BY_CELL? RPAREN
    ;

guiPriority
    : GUI_PRIORITY LPAREN YES RPAREN
    ;

drcRuleMap
    : DRC_RULE_MAP LPAREN
        layerRef
        drcRuleMapFormat?
        name?
        drcRuleMapOption*
      RPAREN
    ;

drcRuleMapFormat
    : formatType layerRef*
    | TEXT_FORMAT
    ;

drcRuleMapOption
    : WITH_PREFIX name
    | WITH_INJECTED_PREFIX name
    | WITH_APPEND name
    | MAX_RESULT (expr | ALL)
    | MAX_VERTEX (expr | ALL)
    | ADD_TEXT name
    | MERGED
    | KEEP_INJECTED_CELL
    | USER_CELL
    | TOP_CELL
    | DB_PRECISION expr
    | DB_MAGNIFY expr
    | INJECT_ARRAY name expr expr expr?
        (BY_POLYGON expr+)?
    | AUTO_INJECT_ARRAY name?
    ;

// ============================================================
// 28. ERC_RESULT, ERC_MAX_RESULT, ERC_SUMMARY, ERC_OUTPUT_CELL_NAME
// ============================================================
ercResultDb
    : ERC_RESULT LPAREN DB name (TEXT_FORMAT)? (KEEP_INJECTED_CELL)? RPAREN
    ;

ercMaxResult
    : ERC_MAX_RESULT LPAREN (expr | ALL) RPAREN
    ;

ercSummary
    : ERC_SUMMARY LPAREN name (OVERWRITE | APPEND)? HIER? RPAREN
    ;

ercOutputCellName
    : ERC_OUTPUT_CELL_NAME LPAREN NO RPAREN
    | ERC_OUTPUT_CELL_NAME LPAREN YES ercOutputCellNameOption* RPAREN
    ;

ercOutputCellNameOption
    : CELL_COORDINATE
    | TRANSFORM_TO_TOP
    | ALL
    ;

// ============================================================
// 29. Shared sub-rules
// ============================================================
op_layer : op_statement | layerRef | LPAREN op_layer RPAREN | LBRACK op_layer RBRACK ;
name : ID | STRING ;
layerRef : ID | INT_LIT | STRING | EDGE ;
formatType : GDSII | OASIS | SPICE | OA ;
constraint : (cmpOp expr)+ ;
expr : expr POW expr
     | expr (MUL | DIV) expr
     | expr (ADD | SUB) expr
     | LPAREN expr RPAREN
     | LPAREN expr COMMA expr RPAREN
     | funcName LPAREN (expr (COMMA expr)*)? RPAREN
     | atom
     | SUB expr;
funcName
    : ID | MAX | INSIDE | OUTSIDE | LEFT | RIGHT | TOP | BOTTOM
    | ALL | EXTEND | COPY | LAYER | NAME | LEVEL | TEXT | PORT
    | REGION | SPACE | SUB | EDGE | CLIP | DELTA | BY | RATIO
    | CONNECT | ATTACH | COMMENT | DIVIDE | DISTANCE | RULE
    | WIDTH | OVERLAP | SQUARE | FIXED | EVEN | ODD | WITH
    | COUNT
    ;
atom : ID | INT_LIT | FLOAT ;
cmpOp : LT | GT | LE | GE | EQ | NE ;

// ============================================================
// GROUP_RULE
// ============================================================
groupRule
    : GROUP_RULE LPAREN name name+ RPAREN
    ;
