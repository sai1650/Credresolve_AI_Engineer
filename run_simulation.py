import threading

from app.models.agent import Agent


def test_only_one_worker_can_reserve_agent():
    agent = Agent(id=1)

    results = []

    def worker(call_id):
        result = agent.reserve(call_id)
        results.append(result)

    threads = [
        threading.Thread(target=worker, args=(i,))
        for i in range(10)
    ]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    successful_reservations = sum(results)

    assert successful_reservations == 1
    assert agent.state.value == "RESERVED"