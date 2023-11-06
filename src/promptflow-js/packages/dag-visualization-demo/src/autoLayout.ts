import { ELK, ElkExtendedEdge, ElkNode, ElkPort, LayoutOptions } from "elkjs";
import { ICanvasData, ICanvasPortInit } from "react-dag-editor";

let elkInstance: ELK;
const getElk = async () => {
  if (!elkInstance) {
    elkInstance = await import("elkjs").then(({ default: ElkConstructor }) => new ElkConstructor());
  }
  return elkInstance;
};

export async function autoLayout<NodeData = never, EdgeData = never, PortData = never>(
  raw: Pick<ICanvasData<NodeData, EdgeData, PortData>, "nodes" | "edges">,
  isCompactMode = true
): Promise<ICanvasData<NodeData, EdgeData, PortData>> {
  const children: ElkNode[] = [];
  const elkEdges: ElkExtendedEdge[] = [];

  raw.nodes.forEach(node => {
    const eastPorts: Array<ICanvasPortInit<PortData>> = [];
    const westPorts: Array<ICanvasPortInit<PortData>> = [];
    const southPorts: Array<ICanvasPortInit<PortData>> = [];
    const northPorts: Array<ICanvasPortInit<PortData>> = [];
    const undefinedSidePorts: Array<ICanvasPortInit<PortData>> = [];

    node.ports?.forEach(p => {
      if (p.position[1] === 1) {
        southPorts.push(p);
      } else if (p.position[1] === 0) {
        northPorts.push(p);
      } else {
        undefinedSidePorts.push(p);
      }
    });

    const ports: ElkPort[] = [];

    eastPorts.forEach((port, index) => {
      const layoutOptions: LayoutOptions = {
        "elk.port.side": "EAST",
        "elk.port.index": `${index}` // The order is assumed as clockwise, starting with the leftmost port on the top side
      };
      ports.push({
        id: `${node.id}:${port.id}`,
        width: 5,
        height: 5,
        layoutOptions
      });
    });

    southPorts.forEach((port, index) => {
      const layoutOptions: LayoutOptions = {
        "elk.port.side": "SOUTH",
        "elk.port.index": `${index}`
      };
      ports.push({
        id: `${node.id}:${port.id}`,
        width: 5,
        height: 5,
        layoutOptions
      });
    });

    westPorts.forEach((port, index) => {
      const layoutOptions: LayoutOptions = {
        "elk.port.side": "WEST",
        "elk.port.index": `${westPorts.length - 1 - index}` // The order is assumed as clockwise, starting with the leftmost port on the top side
      };
      ports.push({
        id: `${node.id}:${port.id}`,
        width: 5,
        height: 5,
        layoutOptions
      });
    });

    northPorts.forEach((port, index) => {
      const layoutOptions: LayoutOptions = {
        "elk.port.side": "NORTH",
        "elk.port.index": `${index}`
      };
      ports.push({
        id: `${node.id}:${port.id}`,
        width: 5,
        height: 5,
        layoutOptions
      });
    });

    undefinedSidePorts.forEach((port, index) => {
      const layoutOptions: LayoutOptions = {
        "elk.port.side": "UNDEFINED",
        "elk.port.index": `${index}`
      };
      ports.push({
        id: `${node.id}:${port.id}`,
        width: 5,
        height: 5,
        layoutOptions
      });
    });

    const elkNode = {
      id: node.id,
      width: node.width ?? 200,
      height: isCompactMode ? 40 : 200,
      ports,
      layoutOptions: {
        "elk.portConstraints": "FIXED_ORDER"
      }
    };

    children.push(elkNode);
  });

  raw.edges.forEach(edge => {
    elkEdges.push({
      id: `edge_${edge.id}`,
      sources: [`${edge.source}:${edge.sourcePortId}`],
      targets: [`${edge.target}:${edge.targetPortId}`],
      sections: []
    });
  });

  const elkGraph: ElkNode = {
    id: "root",
    children,
    edges: elkEdges,
    layoutOptions: {
      "elk.algorithm": "layered",
      "elk.direction": "DOWN",
      "elk.edgeRouting": "SPLINES",
      "elk.spacing.nodeNode": "150",
      "elk.layered.spacing.nodeNodeBetweenLayers": "60"
    }
  };

  const elk = await getElk();
  const layout = await elk.layout(elkGraph);

  return {
    ...raw,
    nodes: raw.nodes.map(n => {
      const nodeLayout = layout.children?.find(i => i.id === n.id);

      if (!nodeLayout || !nodeLayout.x || !nodeLayout.y) {
        return n;
      }
      return {
        ...n,
        x: nodeLayout.x,
        y: nodeLayout.y + 50 // prevent input node from being blocked by tools
      };
    })
  };
}
