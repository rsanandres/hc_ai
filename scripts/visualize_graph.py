#!/usr/bin/env python3
"""Visualize LangGraph multi-agent graph structure.

Generates Mermaid diagrams and ASCII representations of the agent workflow.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from api.agent.multi_agent_graph import create_multi_agent_graph


def print_mermaid_diagram(graph) -> str:
    """Generate and print Mermaid diagram."""
    try:
        mermaid = graph.get_graph().draw_mermaid()
        print("=" * 80)
        print("MERMAID DIAGRAM")
        print("=" * 80)
        print(mermaid)
        print("=" * 80)
        return mermaid
    except Exception as e:
        print(f"Error generating Mermaid diagram: {e}")
        return ""


def print_ascii_diagram(graph) -> str:
    """Generate and print ASCII diagram."""
    try:
        ascii_diag = graph.get_graph().draw_ascii()
        print("\n" + "=" * 80)
        print("ASCII DIAGRAM")
        print("=" * 80)
        print(ascii_diag)
        print("=" * 80)
        return ascii_diag
    except Exception as e:
        print(f"Error generating ASCII diagram: {e}")
        return ""


def print_graph_info(graph):
    """Print detailed graph information."""
    graph_obj = graph.get_graph()
    
    print("\n" + "=" * 80)
    print("GRAPH STRUCTURE INFORMATION")
    print("=" * 80)
    
    # Get nodes
    nodes = graph_obj.nodes
    print(f"\nNodes ({len(nodes)}):")
    for node_name in nodes:
        node_info = nodes[node_name]
        print(f"  - {node_name}")
        if hasattr(node_info, 'bound') and hasattr(node_info.bound, '__name__'):
            print(f"    Function: {node_info.bound.__name__}")
    
    # Get edges
    edges = graph_obj.edges
    print(f"\nEdges ({len(edges)}):")
    for edge in edges:
        source = edge.source if hasattr(edge, 'source') else 'unknown'
        target = edge.target if hasattr(edge, 'target') else 'unknown'
        condition = edge.condition if hasattr(edge, 'condition') else None
        if condition:
            print(f"  - {source} -> {target} (conditional: {condition.__name__ if hasattr(condition, '__name__') else str(condition)})")
        else:
            print(f"  - {source} -> {target}")
    
    # Entry point
    entry_point = graph_obj.first if hasattr(graph_obj, 'first') else None
    if entry_point:
        print(f"\nEntry Point: {entry_point}")
    
    print("=" * 80)


def save_mermaid_to_file(mermaid: str, output_path: Path):
    """Save Mermaid diagram to file."""
    if not mermaid:
        print("No Mermaid diagram to save.")
        return
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Save as .mmd file
    mmd_path = output_path.with_suffix('.mmd')
    with open(mmd_path, 'w') as f:
        f.write(mermaid)
    print(f"\n✓ Saved Mermaid diagram to: {mmd_path}")
    
    # Also save as markdown with code block
    md_path = output_path.with_suffix('.md')
    with open(md_path, 'w') as f:
        f.write("# LangGraph Multi-Agent Graph\n\n")
        f.write("```mermaid\n")
        f.write(mermaid)
        f.write("\n```\n")
    print(f"✓ Saved Markdown with Mermaid to: {md_path}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Visualize LangGraph multi-agent graph structure"
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Output file path for Mermaid diagram (default: prints to stdout)",
    )
    parser.add_argument(
        "--format",
        choices=["mermaid", "ascii", "both", "info"],
        default="both",
        help="Output format (default: both)",
    )
    args = parser.parse_args()
    
    try:
        print("Generating graph...")
        graph = create_multi_agent_graph()
        
        mermaid = ""

        if args.format in ["mermaid", "both"]:
            mermaid = print_mermaid_diagram(graph)

        if args.format in ["ascii", "both"]:
            print_ascii_diagram(graph)
        
        if args.format == "info":
            print_graph_info(graph)
        
        if args.output and mermaid:
            save_mermaid_to_file(mermaid, args.output)
        
        print("\n✓ Graph visualization complete!")
        return 0
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
