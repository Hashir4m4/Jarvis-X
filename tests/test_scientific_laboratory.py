"""
Unit and Integration Tests for Phase 7 — Scientific Intelligence (Prompts 86–100).
"""
import pytest
from backend.core.core import JarvisCore
from backend.scientific.provenance import ScientificProvenance, EvidenceClassification
from backend.scientific.materials import MaterialRecord, MaterialClass, CrystalStructure
from backend.scientific.defects import DefectObservation, DefectType, DefectDimension
from backend.scientific.imaging import MicroscopyModality, PhysicalScaleCalibration
from backend.scientific.experiment_design import DoEMethodology, ExperimentVariable
from backend.scientific.projects import ResearchStage


@pytest.fixture
def core_instance():
    cfg = {
        "storage": {"vault_path": "vault"},
        "voice": {"mode": "MANUAL"}
    }
    return JarvisCore(config=cfg, session_id="phase7_test_session")


def test_phase_7_container_and_core_binding(core_instance):
    assert core_instance.research_lab is not None
    status = core_instance.research_lab.get_laboratory_status()
    assert status["status"] == "OPERATIONAL"
    assert status["subsystems"]["materials_platform"] == "ONLINE"
    assert status["subsystems"]["defect_intelligence"] == "ONLINE"
    assert status["subsystems"]["imaging_platform"] == "ONLINE"
    assert status["subsystems"]["experiment_design"] == "ONLINE"
    assert status["subsystems"]["property_prediction"] == "ONLINE"
    assert status["subsystems"]["literature_intelligence"] == "ONLINE"
    assert status["subsystems"]["data_analysis"] == "ONLINE"
    assert status["subsystems"]["simulation_layer"] == "ONLINE"
    assert status["subsystems"]["hypothesis_engine"] == "ONLINE"
    assert status["subsystems"]["literature_monitoring"] == "ONLINE"
    assert status["subsystems"]["trend_intelligence"] == "ONLINE"
    assert status["subsystems"]["innovation_detection"] == "ONLINE"
    assert status["subsystems"]["patent_intelligence"] == "ONLINE"
    assert status["subsystems"]["project_intelligence"] == "ONLINE"


def test_prompt_86_materials_platform(core_instance):
    service = core_instance.research_lab.materials
    mat = MaterialRecord(
        material_id="mat_graphene_01",
        name="Single-Layer Graphene",
        formula="C",
        composition={"C": 1.0},
        material_class=MaterialClass.TWO_DIMENSIONAL,
        structure=CrystalStructure(space_group="P6/mmm", crystal_system="hexagonal", lattice_parameters={"a": 2.46, "c": 6.70})
    )
    ok, err = service.register_material(mat)
    assert ok is True
    assert err is None

    # Add property with provenance
    service.add_property("mat_graphene_01", "thermal_conductivity", 4800.0, "W/mK", EvidenceClassification.EXPERIMENTAL)
    retrieved = service.get_material("mat_graphene_01")
    assert retrieved is not None
    assert retrieved.properties["thermal_conductivity"]["value"] == 4800.0
    assert retrieved.properties["thermal_conductivity"]["unit"] == "W/mK"


def test_prompt_87_defect_intelligence(core_instance):
    service = core_instance.research_lab.defects
    defect = DefectObservation(
        defect_id="def_vac_01",
        material_id="mat_graphene_01",
        defect_type=DefectType.VACANCY,
        dimension=DefectDimension.POINT,
        detection_method="HRTEM_ALGORITHMIC",
        calibrated_physical_size_nm=0.24,
        confidence_score=0.98
    )
    assert service.record_defect(defect) is True

    # Reject uncalibrated area
    ok, density, err = service.calculate_defect_density("mat_graphene_01", calibrated_area_cm2=0.0)
    assert ok is False
    assert "rejected" in err.lower()

    # Valid calibrated density
    ok_valid, dens, _ = service.calculate_defect_density("mat_graphene_01", calibrated_area_cm2=1.0e-10)
    assert ok_valid is True
    assert dens > 0


def test_prompt_88_scientific_imaging_calibration_enforcement(core_instance):
    service = core_instance.research_lab.imaging
    raw_bytes = b"TEM_SIMULATED_DATA_ARRAY_12345"
    img_rec = service.register_image(
        filename="graphene_hrtem.tif",
        image_bytes=raw_bytes,
        modality=MicroscopyModality.TEM,
        pixel_dimensions=(1024, 1024),
        calibration=PhysicalScaleCalibration(pixels_per_unit=50.0, unit="nm")
    )
    assert img_rec.image_id is not None

    # Measure feature
    ok, size, msg = service.measure_feature_physical_size(img_rec.image_id, 100.0)
    assert ok is True
    assert size == 2.0  # 100px / 50px/nm = 2.0 nm
    assert "2.000 nm" in msg


def test_prompt_89_experiment_design_safety_gates(core_instance):
    service = core_instance.research_lab.experiment_design
    variables = [
        ExperimentVariable(name="Annealing Temperature", variable_type="INDEPENDENT", unit="C", target_or_range=(400, 800)),
        ExperimentVariable(name="Defect Density", variable_type="DEPENDENT", unit="cm^-2", target_or_range=None)
    ]
    plan = service.draft_experiment_plan(
        title="Thermal Defect Annealing Study",
        research_question="How does temperature impact vacancy recombination?",
        variables=variables,
        methodology=DoEMethodology.FULL_FACTORIAL,
        safety_hazards=["High temperature furnace exposure"]
    )
    # Physical execution strictly blocked by default
    assert plan.is_physically_executable is False
    assert plan.human_approved is False

    # Authorize with token
    ok, msg = service.approve_experiment_plan(plan.plan_id, plan.approval_token, reviewer="Senior Metallurgist")
    assert ok is True
    assert plan.human_approved is True


def test_prompt_90_materials_property_prediction(core_instance):
    service = core_instance.research_lab.prediction
    ok, res, msg = service.predict_property(
        formula="GaN",
        property_name="band_gap",
        composition={"Ga": 0.5, "N": 0.5}
    )
    assert ok is True
    assert res.property_name == "band_gap"
    assert res.unit == "eV"
    assert res.provenance.classification == EvidenceClassification.PREDICTED
    assert res.confidence_interval[0] < res.predicted_value < res.confidence_interval[1]


def test_prompt_91_research_paper_intelligence(core_instance):
    service = core_instance.research_lab.literature
    paper = service.ingest_paper_metadata(
        title="Electronic Structure of 2D Materials",
        authors=["Novoselov, K. S.", "Geim, A. K."],
        doi="10.1038/nature04233",
        abstract="We investigate atomic monolayers of carbon.",
        publication_year=2005,
        journal="Nature",
        materials_mentioned=["Graphene"]
    )
    assert paper.paper_id is not None
    added = service.add_extracted_claim(
        paper.paper_id,
        passage="Mobility exceeds 15,000 cm2/Vs at room temperature.",
        page=3,
        section="Results"
    )
    assert added is True
    search_res = service.search_papers("monolayers")
    assert len(search_res) == 1


def test_prompt_92_scientific_data_analysis(core_instance):
    service = core_instance.research_lab.data_analysis
    dataset = [
        {"temp_k": 300.0, "resistivity_ohm_m": 1.2e-4},
        {"temp_k": 350.0, "resistivity_ohm_m": 1.5e-4},
        {"temp_k": 400.0, "resistivity_ohm_m": 1.9e-4},
        {"temp_k": None, "resistivity_ohm_m": 2.4e-4}
    ]
    report = service.validate_dataset(dataset)
    assert report.total_rows == 4
    assert report.missing_value_counts["temp_k"] == 1

    stats = service.calculate_descriptive_stats([10.0, 20.0, 30.0, 40.0, 50.0])
    assert stats.mean == 30.0
    assert stats.median == 30.0


@pytest.mark.asyncio
async def test_prompt_93_simulation_lifecycle(core_instance):
    service = core_instance.research_lab.simulation
    job = service.create_simulation_job(
        name="Graphene Ground State DFT",
        engine="VASP_DFT_SIMULATOR",
        parameters={"ecut_ev": 500, "kpoints": "12x12x1"}
    )
    assert job.status.value == "VALIDATED"

    ok, msg = await service.execute_simulation(job.job_id)
    assert ok is True
    assert job.convergence_achieved is True
    assert job.status.value == "COMPLETED"


def test_prompt_94_hypothesis_falsification(core_instance):
    service = core_instance.research_lab.hypotheses
    # Fails if no falsifiable prediction
    ok_fail, _, _ = service.formulate_hypothesis(
        scientific_question="Why does resistivity rise?",
        proposed_explanation="Unknown electron scattering.",
        supporting_observations=["Resistivity slope is positive."],
        falsifiable_predictions=[]
    )
    assert ok_fail is False

    # Valid hypothesis
    ok_valid, hyp, _ = service.formulate_hypothesis(
        scientific_question="Why does resistivity rise?",
        proposed_explanation="Acoustic phonon scattering dominates above 150 K.",
        supporting_observations=["T-linear resistivity observed."],
        falsifiable_predictions=["Doping will decrease mobility proportional to T^1."]
    )
    assert ok_valid is True
    assert hyp.provenance.classification == EvidenceClassification.HYPOTHESIS


def test_prompt_95_monitoring_and_duplicate_suppression(core_instance):
    service = core_instance.research_lab.monitoring
    topic = service.create_topic("Perovskites", ["perovskite", "halide", "photovoltaic"])

    matches1 = service.process_incoming_publication("10.1016/j.solmat.2026.01", "Halide perovskite stability", "Degradation mechanisms in halides.")
    assert len(matches1) == 1

    # Duplicate dropped
    matches_dup = service.process_incoming_publication("10.1016/j.solmat.2026.01", "Halide perovskite stability", "Degradation mechanisms in halides.")
    assert len(matches_dup) == 0


def test_prompt_96_to_100_integrated_laboratory_flow(core_instance):
    lab = core_instance.research_lab

    # Prompt 96: Trend
    trend = lab.trends.analyze_trend("Solid State Batteries", {2022: 120, 2023: 210, 2024: 380, 2025: 590}, ["sulfide electrolyte", "anode-free"])
    assert trend.growth_rate_percent > 0

    # Prompt 97: Innovation
    ok_opp, opp, _ = lab.innovation.register_opportunity(
        problem_statement="Dendrite penetration short-circuits lithium anodes.",
        target_application="Electric Aviation Batteries",
        identified_research_gap="Interfacial mechanical elasticity at current densities > 10 mA/cm².",
        supporting_evidence=["Nature Materials 2025 review."],
        technical_feasibility_score=0.72,
        commercial_potential_score=0.95,
        major_risks=["Electrochemical stability window mismatch."]
    )
    assert ok_opp is True

    # Prompt 98: Patent Prior Art
    lab.patents.index_patent(
        patent_number="US11223344B2",
        title="Composite Solid Electrolyte Membrane",
        assignee="Quantum Battery Corp",
        filing_date="2022-04-10",
        publication_date="2024-01-15",
        abstract="A polymer-ceramic composite electrolyte having high ionic conductivity.",
        claims=["A solid electrolyte comprising ceramic particles."],
        classification_codes=["H01M10/056"]
    )
    patents = lab.patents.search_prior_art("composite electrolyte")
    assert len(patents) == 1

    # Prompt 99: Project Intelligence
    project = lab.projects.create_project("NextGen Graphene Supercapacitor", "Achieve 150 Wh/kg energy density.")
    assert project.stage == ResearchStage.IDEA
    lab.projects.advance_project_stage(project.project_id, ResearchStage.EXPERIMENT_DESIGN)
    lab.projects.link_artifact(project.project_id, "material", "mat_graphene_01")
    assert "mat_graphene_01" in project.associated_materials

    # Prompt 100: Unified Laboratory Inquiry Execution
    status = lab.get_laboratory_status()
    assert status["lab_mode_active"] is True
