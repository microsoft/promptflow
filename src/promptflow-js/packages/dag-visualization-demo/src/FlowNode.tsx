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
      <rect x1={node.x} x2={node.x + width} y1={node.y} y2={node.y + height} stroke="blue"></rect>
      <text x={node.x} y={node.y} height={height} width={width} textAnchor="center">{node.id}</text>
    </g>
  );
}