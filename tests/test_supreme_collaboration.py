from services.supreme.collaboration import ProjectTask, completion_ratio, ready_tasks


def test_initial_independent_work_is_parallel_ready():
    tasks = (
        ProjectTask("inventory", "Inventory Seldrune from beginning"),
        ProjectTask("bench", "Establish baseline benchmarks"),
        ProjectTask("integrate", "Integrate SUPREME", ("inventory", "bench")),
    )
    ready = ready_tasks(tasks, frozenset())
    assert {task.task_id for task in ready} == {"inventory", "bench"}


def test_completed_dependencies_unlock_integration():
    task = ProjectTask("integrate", "Integrate SUPREME", ("inventory", "bench"))
    assert ready_tasks((task,), frozenset({"inventory", "bench"})) == (task,)


def test_completion_ratio():
    tasks = (ProjectTask("a", "A"), ProjectTask("b", "B"))
    assert completion_ratio(tasks, frozenset({"a"})) == 0.5
