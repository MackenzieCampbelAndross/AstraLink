"""Main entry point for Astra Link Member 2 tracking system."""

import argparse
import json
import sys
from pathlib import Path

from astra_link_tracking.models.config import TrackingSystemConfig
from astra_link_tracking.simulation.closed_loop import ClosedLoopSimulation


def run_closed_loop_simulation(config: TrackingSystemConfig, trajectory_type: str = "stationary",
                              duration: float = 10.0, seed: int = 42):
    """Run closed-loop simulation.
    
    Args:
        config: Tracking system configuration
        trajectory_type: Type of trajectory
        duration: Simulation duration
        seed: Random seed
    """
    print(f"Running closed-loop simulation...")
    print(f"  Trajectory: {trajectory_type}")
    print(f"  Duration: {duration}s")
    print(f"  Seed: {seed}")
    print()
    
    # Create simulation
    sim = ClosedLoopSimulation(
        config=config,
        trajectory_type=trajectory_type,
        duration=duration,
        dt=0.05,
        seed=seed,
        measurement_noise_std=0.1
    )
    
    # Run simulation
    result = sim.run()
    
    # Get summary
    summary = sim.get_summary()
    
    # Print results
    print("=== Simulation Results ===")
    print(f"Duration: {summary['duration']:.2f}s")
    print(f"Steps: {summary['steps']}")
    print(f"Final Error: {summary['final_error']:.4f}°")
    print(f"Mean Error: {summary['mean_error']:.4f}°")
    print(f"Max Error: {summary['max_error']:.4f}°")
    print(f"Min Error: {summary['min_error']:.4f}°")
    print(f"Final Mode: {summary['final_mode']}")
    print(f"Final Camera Pan: {summary['camera_pan']:.4f}°")
    print(f"Final Camera Tilt: {summary['camera_tilt']:.4f}°")
    print()
    
    # Print trajectory information
    print("=== Trajectory Information ===")
    if result.history:
        first = result.history[0]
        last = result.history[-1]
        print(f"Initial Target: ({first.target_pan:.2f}°, {first.target_tilt:.2f}°)")
        print(f"Final Target: ({last.target_pan:.2f}°, {last.target_tilt:.2f}°)")
        print(f"Initial Error: ({first.error_pan:.2f}°, {first.error_tilt:.2f}°)")
        print(f"Final Error: ({last.error_pan:.2f}°, {last.error_tilt:.2f}°)")
    print()
    
    print("Simulation complete.")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Astra Link Member 2 Tracking System")
    parser.add_argument(
        "--config",
        type=str,
        default="config/default_config.json",
        help="Path to configuration file"
    )
    parser.add_argument(
        "--scenario",
        type=str,
        choices=["closed_loop"],
        help="Simulation scenario to run"
    )
    parser.add_argument(
        "--trajectory",
        type=str,
        default="stationary",
        choices=["stationary", "linear", "circular", "figure8", "sinusoidal", "random", "spiral"],
        help="Trajectory type for closed-loop simulation"
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=10.0,
        help="Simulation duration in seconds"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility"
    )
    
    args = parser.parse_args()
    
    # Load configuration
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Error: Configuration file not found: {config_path}")
        sys.exit(1)
    
    config = TrackingSystemConfig.from_json_file(config_path)
    
    if args.scenario == "closed_loop":
        run_closed_loop_simulation(
            config=config,
            trajectory_type=args.trajectory,
            duration=args.duration,
            seed=args.seed
        )
    else:
        print("Error: Please specify a scenario with --scenario")
        print("Available scenarios: closed_loop")
        sys.exit(1)


if __name__ == "__main__":
    main()
