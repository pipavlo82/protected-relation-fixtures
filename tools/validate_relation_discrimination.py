from relation_discrimination import RelationDiscriminationError, validate_suite_file


def main() -> int:
    try:
        report = validate_suite_file()
    except RelationDiscriminationError as exc:
        print(f"relation discrimination: FAIL: {exc}")
        return 1
    for axis, result in report["matrix"].items():
        print(f"{axis}: {result['status']}")
    print(
        "relation discrimination: PASS "
        f"({report['separated_axes']}/{report['required_axes']} axes; "
        f"{report['witnesses']} witnesses)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
