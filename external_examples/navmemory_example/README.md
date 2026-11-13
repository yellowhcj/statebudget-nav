# Separate sparse navigation-memory example

MIT-licensed conventional example, written by the software author. It tests
reuse of StateBudget-Nav rather than novelty or independent scientific adoption.
Install the two supplied wheels. See the [MOVINGAI guide](../../MOVINGAI.md) for commands.

The controller imports only Python standard-library modules. Its initializer
uses the public MovingAI parser to obtain the declared destination; no map cell
or oracle value enters the initial state. The goal occupies five bytes, each
known-cell record five bytes, and insertion order is charged by record order.
Observations update records; transient optimistic A* selects the current action;
oldest records are removed until the state fits. This retains original FIFO
age, unlike LRU. No extra state survives in globals, files or diagnostics.

The example assumes exact localization, static free/blocked grids and a known
destination. Search workspace and code are separate from persistent payload.
It supplies no guarantee of success or advantage over compressed maps/topology.
