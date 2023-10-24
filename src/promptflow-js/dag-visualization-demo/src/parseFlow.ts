/* eslint-disable @typescript-eslint/naming-convention */
import { ICanvasNode } from "react-dag-editor";
import { FlowNode, FlowNodeVariant, FlowSnapshot, IPromptFlowCanvasData, IPromptFlowCanvasEdge, IPromptFlowCanvasNode } from "./types";

export const CENTER_DUMMY_ANCHOR = "center-dummy-port";
export const FLOW_INPUT_NODE_ID = "flow-input-node";
export const FLOW_OUTPUT_NODE_ID = "flow-output-node";
export const NODE_INPUT_PORT_ID = "node-input-port";
export const NODE_OUTPUT_PORT_ID = "node-output-port";
export const FLOW_INPUT_REF_NAME_FLOW = "flow";
export const FLOW_INPUT_REF_NAME_INPUT = "inputs";
export const FLOW_INPUT_NODE_NAME = "inputs";
export const FLOW_OUTPUT_NODE_NAME = "outputs";

export const FlowInputNodeHeight = 40;
export const FlowInputNodeWidth = 60;
export const FlowNodeWidth = 220;
export const FlowNodeBaseHeight = 50;

const revValueRegex = /^\$\{(\S+)\}$/;
export const getRefValueFromRaw = (raw: string | number | object | void): string | undefined => {
  return `${raw ?? ""}`?.match(revValueRegex)?.[1];
};


export const isFlowInput = (variableName: string): boolean => {
  return [FLOW_INPUT_REF_NAME_FLOW, FLOW_INPUT_REF_NAME_INPUT].includes(variableName);
};

export const isFlowOutput = (variableName: string): boolean => {
  return FLOW_OUTPUT_NODE_NAME === variableName;
};

export const fromDagNodeToCanvasNode = (dagNode: FlowNode): IPromptFlowCanvasNode => {
  const canvasNode: IPromptFlowCanvasNode = {
    id: dagNode.name ?? "",
    name: dagNode.name,
    x: 0,
    y: 0,
    ports: [
      {
        id: NODE_INPUT_PORT_ID,
        name: "input",
        isInputDisabled: false,
        isOutputDisabled: true,
        position: [0.5, 0]
      },
      {
        id: NODE_OUTPUT_PORT_ID,
        name: "output",
        isInputDisabled: true,
        isOutputDisabled: false,
        position: [0.5, 1]
      }
    ],
    data: {
      type: dagNode.type
    }
  };

  return canvasNode;
};

// tslint:disable-next-line:export-name
export const fromDagToCanvasDataUnlayouted = (dag: FlowSnapshot): IPromptFlowCanvasData => {
  const flowInputNode: IPromptFlowCanvasNode = {
    id: FLOW_INPUT_NODE_ID,
    name: FLOW_INPUT_NODE_NAME,
    x: 0,
    y: 0,
    ports: [
      {
        id: NODE_OUTPUT_PORT_ID,
        name: "output",
        isInputDisabled: true,
        isOutputDisabled: false,
        position: [0.5, 1]
      }
    ]
  };
  const flowOutputNode: IPromptFlowCanvasNode = {
    id: FLOW_OUTPUT_NODE_ID,
    name: FLOW_OUTPUT_NODE_NAME,
    x: 0,
    y: 0,
    ports: [
      {
        id: NODE_INPUT_PORT_ID,
        name: "input",
        isInputDisabled: false,
        isOutputDisabled: true,
        position: [0.5, 0]
      }
    ]
  };
  const canvasNodes: IPromptFlowCanvasNode[] = [flowInputNode, flowOutputNode];
  const canvasEdges: IPromptFlowCanvasEdge[] = [];

  // nodes, outputs, inputs maybe null or undefined. so use `||` instead of `??` here
  const nodes = dag.nodes || [];
  const outputs = dag.outputs || {};
  const node_variants = dag.node_variants as { [key: string]: FlowNodeVariant } | undefined;
  nodes.forEach(node => {
    let dagNode = node;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    if ((dagNode as any)?.use_variants) {
      const nodeVariant = node_variants?.[dagNode.name ?? ""] ?? {};
      const { default_variant_id, variants } = nodeVariant;
      dagNode = variants?.[default_variant_id ?? ""].node ?? dagNode;
      dagNode = {
        ...dagNode,
        name: node.name
      };
    }

    const addEdgeByInputValue = (inputValue: string | undefined) => {
      const valueRef = getRefValueFromRaw(inputValue);

      const [prevNodeName] = valueRef?.split(".") ?? [];
      const prevNode = (nodes as FlowNode[]).find(n => n.name === prevNodeName);

      if (prevNode) {
        const canvasEdge: IPromptFlowCanvasEdge = {
          id: `${prevNodeName}-${dagNode.name}`,
          source: prevNodeName,
          sourcePortId: NODE_OUTPUT_PORT_ID,
          target: dagNode.name ?? "",
          targetPortId: NODE_INPUT_PORT_ID
        };

        if (canvasEdges.filter(e => e.id === canvasEdge.id).length === 0) {
          canvasEdges.push(canvasEdge);
        }
      } else if (isFlowInput(prevNodeName)) {
        const canvasEdge: IPromptFlowCanvasEdge = {
          id: `${FLOW_INPUT_NODE_ID}-${dagNode.name}`,
          source: FLOW_INPUT_NODE_ID,
          sourcePortId: NODE_OUTPUT_PORT_ID,
          target: dagNode.name ?? "",
          targetPortId: NODE_INPUT_PORT_ID
        };

        if (canvasEdges.filter(e => e.id === canvasEdge.id).length === 0) {
          canvasEdges.push(canvasEdge);
        }
      }
    };

    Object.keys(dagNode.inputs ?? {}).forEach(inputKey => {
      const inputValue = dagNode.inputs?.[inputKey];
      addEdgeByInputValue(inputValue);
    });
    addEdgeByInputValue(dagNode?.activate?.when);

    canvasNodes.push(fromDagNodeToCanvasNode(dagNode));
  });

  Object.keys(outputs).forEach(dagOutputKey => {
    const dagOutput = outputs[dagOutputKey];
    const outputRef = getRefValueFromRaw(dagOutput.reference);
    const [outputRefNodeName] = outputRef?.split(".") ?? [];

    if (outputRefNodeName && canvasNodes.find(n => n.id === outputRefNodeName)) {
      canvasEdges.push({
        id: `${outputRefNodeName}-${FLOW_OUTPUT_NODE_ID}`,
        source: outputRefNodeName,
        sourcePortId: NODE_OUTPUT_PORT_ID,
        target: FLOW_OUTPUT_NODE_ID,
        targetPortId: NODE_INPUT_PORT_ID
      });
    }
  });

  return {
    nodes: canvasNodes,
    edges: canvasEdges
  };
};

export const isInitFlow = <NodeData, PortData>(nodes: ReadonlyArray<ICanvasNode<NodeData, PortData>>): boolean => {
  if (nodes.length !== 2) {
    return false;
  }
  return nodes.some(n => n.id === FLOW_INPUT_NODE_ID) && nodes.some(n => n.id === FLOW_OUTPUT_NODE_ID);
};
