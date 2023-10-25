import React from "react";
import { ReactDagEditor, Graph, useGraphReducer, GraphModel, IGraphConfig, GraphConfigBuilder, INodeConfig, INodeDrawArgs, getRectHeight, getRectWidth, ICanvasNode, GraphCanvasEvent, CanvasMouseMode } from "react-dag-editor";
import { ToolType } from "./types";
import { FlowNode } from "./FlowNode";
import Editor from '@monaco-editor/react';
import { fromDagToCanvasDataUnlayouted } from "./parseFlow";
import { parse } from "yaml";
import { autoLayout } from "./autoLayout";

export interface INodeRunStatus {
  node: string;
  /**
   * @deprecated
   */
  flow_run_id: string;
  /**
   * @deprecated
   */
  run_id: string;
  status: string;
  inputs: Record<string, any>;
  /**
   * @deprecated
   */
  result: any;
  output: any; // same with .result, will use this field
  /**
   * @deprecated
   */
  parent_run_id: string;
  index: number;
  variant_id?: string;
  /**
   * @deprecated
   */
  metrics?: any; // todo
  system_metrics?: {
    duration?: number;
    total_tokens?: number;
  };
  /**
   * @deprecated
   */
  request?: any;
  start_time?: string;
  end_time?: string;
  cached_run_id?: string | null;
  logs?: {
    stderr?: string;
    stdout?: string;
  };
}

export interface INodeExtData {
  toolType: ToolType | undefined;
  providerIconName: string | undefined;
  toolsIcon: string | undefined;
  statusColor: string | undefined;
  statusIcon: string | JSX.Element | undefined;
  nodeRuns: INodeRunStatus[];
  nodeParams: Record<string, string | undefined>;
  hasVariants: boolean | undefined;
  isReduce: boolean | undefined;
  nodeColor: string | undefined;
  /**
   * Only for bulk run details page, get node status count from index service
   */
  nodeStatusCount?: { [key: string]: number };
  skip: {
    hasSkipConfig: boolean;
    tooltip: string | JSX.Element | undefined;
    onClickSkipConfig?(nodeId: string): void;
  };
  activate: {
    hasActivateConfig: boolean;
    tooltip: string | JSX.Element | undefined;
    onClickActivateConfig?(nodeId: string): void;
  };
  renderActions?(nodeId: string): JSX.Element | undefined;
}
export const FlowNodeWidth = 220;
export const FlowNodeBaseHeight = 50;

class FlowNodeConfig implements INodeConfig {
  public render(args: INodeDrawArgs<never, never>): React.ReactNode {
    const node = args.model;
    const height = getRectHeight(this, args.model);
    const width = getRectWidth(this, args.model);

    return (
      <FlowNode
        node={node}
        height={height}
        width={width}
      />
    );
  }

  public getMinWidth(_rect: Partial<ICanvasNode<never, never>>): number {
    return FlowNodeWidth;
  }

  public getMinHeight(_rect: Partial<ICanvasNode<never, never>>): number {
    return FlowNodeBaseHeight;
  }
}

export const Dag: React.FC = () => {
  const flowNodeConfig = new FlowNodeConfig();
  const graphConfig = GraphConfigBuilder.default()
    .registerNode(node => {
      return flowNodeConfig;
    })
    .build() as IGraphConfig<never, never, never>;
  const [state, dispatch] = useGraphReducer({
    settings: {
      graphConfig
    }
  }, undefined);

  const editorRef = React.useRef(null);

  return (
    <>
      <Editor
        height="30vh"
        defaultLanguage="yaml"
        defaultValue=""
        onMount={editor => {
          editorRef.current = editor;
        }}
        onChange={async value => {
          if (!value) {
            return;
          }
          try {
            const json = parse(value);
            dispatch({
              type: GraphCanvasEvent.SetData,
              data: GraphModel.fromJSON(await autoLayout(fromDagToCanvasDataUnlayouted(json)))
            });
          } catch {

          }
        }}
      />
      <ReactDagEditor
        style={{ width: "900px", height: "600px", backgroundColor: "#ccc" }}
        state={state}
        // @ts-ignore
        dispatch={dispatch}
      >
        <Graph canvasMouseMode={CanvasMouseMode.Pan} />
      </ReactDagEditor>
    </>
  );
}