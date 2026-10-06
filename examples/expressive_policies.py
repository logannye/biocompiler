"""Run with an installed package, including outside the checkout."""
from biocompiler.policy import check
from biocompiler.policy.examples import NAMES, build_request


def main() -> None:
    for name in NAMES:
        report = check(build_request(name))
        if report.status != "complete":
            raise RuntimeError(report.to_dict())
        print(f"{name}: structurally complete; semantics and target support unassessed")


if __name__ == "__main__":
    main()
