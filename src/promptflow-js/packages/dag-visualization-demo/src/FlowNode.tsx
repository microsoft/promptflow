import React from "react";
import { IPromptFlowCanvasNode } from "./types";

interface IFlowNodeProps {
  node: IPromptFlowCanvasNode;
  height: number;
  width: number;
}

export const FlowNode: React.FC<IFlowNodeProps> = ({ node, width, height }) => {
  return (
    <g>
      <rect x={node.x} width={width} y={node.y} height={height} stroke="blue" strokeWidth={1} fill="none"></rect>
      <text x={node.x} y={node.y} height={height} width={width} textAnchor="center">{node.id}</text>
    </g>
  );
}