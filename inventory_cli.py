from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

from inventory_client import InventoryClient
from inventory_client.config import (
    CONFIG_PATH,
    get_profile,
    load_config,
    set_default_profile,
    set_profile_value,
)
from inventory_client.errors import EXIT_ARGUMENT, EXIT_BUSINESS, ArgumentUsageError, ClientError


GLOBAL_VALUE_OPTIONS = {"--server", "--token", "--profile", "--timeout"}
GLOBAL_FLAG_OPTIONS = {"--json", "--pretty", "--quiet", "--verbose"}


def extract_global_options(argv: list[str]) -> tuple[dict[str, Any], list[str]]:
    options: dict[str, Any] = {
        "server": None,
        "token": None,
        "profile": None,
        "timeout": None,
        "json": False,
        "pretty": False,
        "quiet": False,
        "verbose": False,
    }
    remaining: list[str] = []
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg in GLOBAL_VALUE_OPTIONS:
            if index + 1 >= len(argv):
                raise argparse.ArgumentError(None, f"{arg} requires a value")
            options[arg[2:].replace("-", "_")] = argv[index + 1]
            index += 2
            continue
        if any(arg.startswith(f"{name}=") for name in GLOBAL_VALUE_OPTIONS):
            name, value = arg.split("=", 1)
            options[name[2:].replace("-", "_")] = value
            index += 1
            continue
        if arg in GLOBAL_FLAG_OPTIONS:
            options[arg[2:].replace("-", "_")] = True
            index += 1
            continue
        remaining.append(arg)
        index += 1
    return options, remaining


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="inventory",
        description="Components Inventory remote automation CLI",
        epilog=(
            "Global options may appear anywhere: --server, --token, --profile, "
            "--json, --pretty, --quiet, --timeout, --verbose"
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    config = subparsers.add_parser("config")
    config_sub = config.add_subparsers(dest="config_command", required=True)
    set_server = config_sub.add_parser("set-server")
    set_server.add_argument("profile")
    set_server.add_argument("url")
    set_token = config_sub.add_parser("set-token")
    set_token.add_argument("profile")
    set_token.add_argument("token")
    use = config_sub.add_parser("use")
    use.add_argument("profile")
    show = config_sub.add_parser("show")
    show.add_argument("profile", nargs="?")
    show.add_argument("--show-token", action="store_true")

    subparsers.add_parser("ping")
    subparsers.add_parser("stats")

    components = subparsers.add_parser("components")
    comp_sub = components.add_subparsers(dest="components_command", required=True)
    comp_list = comp_sub.add_parser("list")
    comp_list.add_argument("--keyword")
    comp_list.add_argument("--category-id", type=int)
    comp_list.add_argument("--box-id", type=int)
    comp_list.add_argument("--tag")
    comp_list.add_argument("--low-stock", action="store_true")
    comp_list.add_argument("--page", type=int, default=1)
    comp_list.add_argument("--page-size", type=int, default=20)
    comp_get = comp_sub.add_parser("get")
    comp_get.add_argument("component_id", type=int)
    comp_create = comp_sub.add_parser("create")
    add_component_payload_args(comp_create, require_name=True)
    comp_update = comp_sub.add_parser("update")
    comp_update.add_argument("component_id", type=int)
    add_component_payload_args(comp_update, require_name=False)
    comp_delete = comp_sub.add_parser("delete")
    comp_delete.add_argument("component_id", type=int)
    comp_delete.add_argument("--yes", action="store_true")

    boxes = subparsers.add_parser("boxes")
    boxes_sub = boxes.add_subparsers(dest="boxes_command", required=True)
    boxes_sub.add_parser("list")
    box_get = boxes_sub.add_parser("get")
    box_get.add_argument("box_id", type=int)
    box_grid = boxes_sub.add_parser("grid")
    box_grid.add_argument("box_id", type=int)

    stock = subparsers.add_parser("stock")
    stock_sub = stock.add_subparsers(dest="stock_command", required=True)
    stock_in = stock_sub.add_parser("in")
    stock_in.add_argument("component_id", type=int)
    stock_in.add_argument("--quantity", type=int, required=True)
    stock_in.add_argument("--reason")
    stock_out = stock_sub.add_parser("out")
    stock_out.add_argument("component_id", type=int)
    stock_out.add_argument("--quantity", type=int, required=True)
    stock_out.add_argument("--reason")
    stock_logs = stock_sub.add_parser("logs")
    stock_logs.add_argument("component_id", type=int)
    stock_logs.add_argument("--page", type=int, default=1)
    stock_logs.add_argument("--page-size", type=int, default=20)
    return parser


def add_component_payload_args(parser: argparse.ArgumentParser, *, require_name: bool) -> None:
    parser.add_argument("--name", required=require_name)
    parser.add_argument("--category-id", type=int)
    parser.add_argument("--model")
    parser.add_argument("--package")
    parser.add_argument("--value", dest="nominal_value")
    parser.add_argument("--voltage")
    parser.add_argument("--current")
    parser.add_argument("--power")
    parser.add_argument("--tolerance")
    parser.add_argument("--material")
    parser.add_argument("--manufacturer")
    parser.add_argument("--quantity", type=int)
    parser.add_argument("--min-stock", type=int)
    parser.add_argument("--box-id", type=int)
    parser.add_argument("--compartment-id", type=int)
    parser.add_argument("--cell-row", type=int)
    parser.add_argument("--cell-col", type=int)
    parser.add_argument("--description")
    parser.add_argument("--tag", action="append", dest="tags")
    parser.add_argument("--extra-spec", action="append", default=[])


def component_payload(args: argparse.Namespace) -> dict[str, Any]:
    mapping = {
        "name": "name",
        "category_id": "category_id",
        "model": "model",
        "package": "package",
        "nominal_value": "nominal_value",
        "voltage": "voltage_rating",
        "current": "current_rating",
        "power": "power_rating",
        "tolerance": "tolerance",
        "material": "material_type",
        "manufacturer": "manufacturer",
        "quantity": "quantity",
        "min_stock": "min_stock",
        "box_id": "box_id",
        "compartment_id": "compartment_id",
        "cell_row": "cell_row",
        "cell_col": "cell_col",
        "description": "description",
        "tags": "tags",
    }
    payload: dict[str, Any] = {}
    for arg_name, field_name in mapping.items():
        value = getattr(args, arg_name, None)
        if value is not None:
            payload[field_name] = value
    extra_specs: dict[str, str] = {}
    for item in getattr(args, "extra_spec", []) or []:
        if "=" not in item:
            raise ArgumentUsageError(f"invalid --extra-spec value, expected key=value: {item}")
        key, value = item.split("=", 1)
        if key:
            extra_specs[key] = value
    if extra_specs:
        payload["extra_specs"] = extra_specs
    return payload


def resolve_connection(global_options: dict[str, Any]) -> tuple[str, str, float, str]:
    config = load_config()
    profile_name = (
        global_options.get("profile")
        or os.environ.get("INVENTORY_PROFILE")
        or config.get("default_profile")
        or ""
    )
    profile = get_profile(config, profile_name)
    server = (
        global_options.get("server")
        or os.environ.get("INVENTORY_SERVER")
        or profile.get("server")
        or "http://localhost:5000"
    )
    token = (
        global_options.get("token")
        or os.environ.get("INVENTORY_TOKEN")
        or profile.get("token")
        or ""
    )
    timeout_value = global_options.get("timeout") or os.environ.get("INVENTORY_TIMEOUT") or 30
    return server, token, float(timeout_value), profile_name


def make_client(global_options: dict[str, Any]) -> InventoryClient:
    server, token, timeout, _profile = resolve_connection(global_options)
    return InventoryClient(server, token=token, timeout=timeout)


def envelope(data: Any, message: str = "ok") -> dict[str, Any]:
    return {"code": 0, "data": data, "message": message}


def print_response(response: dict[str, Any], global_options: dict[str, Any], view: str = "generic") -> None:
    if global_options.get("json") or global_options.get("pretty"):
        print(json.dumps(response, ensure_ascii=False, indent=2 if global_options.get("pretty") else None))
        return
    if global_options.get("quiet"):
        message = response.get("message")
        if message:
            print(message)
        return
    data = response.get("data")
    if view == "components-list":
        print_table((data or {}).get("items", []), ["id", "name", "nominal_value", "package", "quantity", "box_name", "cell_label"])
    elif view == "boxes-list":
        print_table(data or [], ["id", "name", "rows", "cols", "used_slots", "total_slots", "total_quantity"])
    elif view == "stock-logs":
        print_table((data or {}).get("items", []), ["id", "component_id", "component_name", "operation_type", "quantity_change", "quantity_after", "reason"])
    elif isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False)
            print(f"{key}: {value}")
    elif isinstance(data, list):
        print_table(data, sorted({key for item in data if isinstance(item, dict) for key in item.keys()}))
    else:
        print(response.get("message", "ok"))


def print_table(rows: list[dict[str, Any]], columns: list[str]) -> None:
    if not rows:
        print("(empty)")
        return
    rendered = [[stringify(row.get(column)) for column in columns] for row in rows]
    widths = [
        max(len(column), *(len(row[index]) for row in rendered))
        for index, column in enumerate(columns)
    ]
    print("  ".join(column.ljust(widths[index]) for index, column in enumerate(columns)))
    print("  ".join("-" * width for width in widths))
    for row in rendered:
        print("  ".join(value.ljust(widths[index]) for index, value in enumerate(row)))


def stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)


def confirm_delete(label: str, yes: bool) -> None:
    if yes:
        return
    if not sys.stdin.isatty():
        raise ArgumentUsageError(f"{label} requires --yes in non-interactive mode")
    answer = input(f"Delete {label}? Type 'yes' to continue: ")
    if answer.strip().lower() != "yes":
        raise ArgumentUsageError("operation cancelled")


def handle_config(args: argparse.Namespace, global_options: dict[str, Any]) -> int:
    if args.config_command == "set-server":
        set_profile_value(args.profile, "server", args.url)
        print_response(envelope({"profile": args.profile, "server": args.url, "config_path": str(CONFIG_PATH)}), global_options)
    elif args.config_command == "set-token":
        set_profile_value(args.profile, "token", args.token)
        print_response(envelope({"profile": args.profile, "token": "***", "config_path": str(CONFIG_PATH)}), global_options)
    elif args.config_command == "use":
        set_default_profile(args.profile)
        print_response(envelope({"default_profile": args.profile, "config_path": str(CONFIG_PATH)}), global_options)
    elif args.config_command == "show":
        config = load_config()
        profile_name = args.profile or config.get("default_profile") or ""
        profile = get_profile(config, profile_name)
        data = {
            "profile": profile_name,
            "server": profile.get("server", ""),
            "token": profile.get("token", "") if args.show_token else ("***" if profile.get("token") else ""),
            "config_path": str(CONFIG_PATH),
        }
        print_response(envelope(data), global_options)
    return 0


def run(args: argparse.Namespace, global_options: dict[str, Any]) -> int:
    if args.command == "config":
        return handle_config(args, global_options)

    client = make_client(global_options)
    if args.command == "ping":
        response = client.ping()
        print_response(envelope({"reachable": True, "stats": response.get("data")}), global_options)
    elif args.command == "stats":
        print_response(client.stats(), global_options)
    elif args.command == "components":
        if args.components_command == "list":
            response = client.list_components(
                keyword=args.keyword,
                category_id=args.category_id,
                box_id=args.box_id,
                tag=args.tag,
                low_stock="1" if args.low_stock else None,
                page=args.page,
                page_size=args.page_size,
            )
            print_response(response, global_options, "components-list")
        elif args.components_command == "get":
            print_response(client.get_component(args.component_id), global_options)
        elif args.components_command == "create":
            print_response(client.create_component(component_payload(args)), global_options)
        elif args.components_command == "update":
            print_response(client.update_component(args.component_id, component_payload(args)), global_options)
        elif args.components_command == "delete":
            confirm_delete(f"component {args.component_id}", args.yes)
            print_response(client.delete_component(args.component_id), global_options)
    elif args.command == "boxes":
        if args.boxes_command == "list":
            print_response(client.list_boxes(), global_options, "boxes-list")
        elif args.boxes_command == "get":
            print_response(client.get_box(args.box_id), global_options)
        elif args.boxes_command == "grid":
            print_response(client.get_box_grid(args.box_id), global_options)
    elif args.command == "stock":
        if args.stock_command == "in":
            print_response(client.stock_in(args.component_id, args.quantity, args.reason), global_options)
        elif args.stock_command == "out":
            print_response(client.stock_out(args.component_id, args.quantity, args.reason), global_options)
        elif args.stock_command == "logs":
            print_response(client.stock_logs(args.component_id, args.page, args.page_size), global_options, "stock-logs")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        global_options, remaining = extract_global_options(argv)
    except argparse.ArgumentError as exc:
        print(json.dumps({"code": 1, "data": None, "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return EXIT_ARGUMENT
    parser = make_parser()
    try:
        args = parser.parse_args(remaining)
        return run(args, global_options)
    except SystemExit as exc:
        return int(exc.code)
    except ClientError as exc:
        response = exc.response or {"code": 1, "data": None, "message": exc.message}
        if global_options.get("json") or global_options.get("pretty"):
            print(json.dumps(response, ensure_ascii=False, indent=2 if global_options.get("pretty") else None), file=sys.stderr)
        else:
            print(response.get("message") or exc.message, file=sys.stderr)
        return exc.exit_code
    except KeyboardInterrupt:
        print("cancelled", file=sys.stderr)
        return EXIT_BUSINESS


if __name__ == "__main__":
    raise SystemExit(main())
