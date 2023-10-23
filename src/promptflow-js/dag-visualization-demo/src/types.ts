export interface FlowNode {
  /**
   *
   * @type {string}
   * @memberof FlowNode
   */
  name?: string | undefined;
  /**
   *
   * @type {ToolType}
   * @memberof FlowNode
   */
  type?: ToolType;
  /**
   *
   * @type {NodeSource}
   * @memberof FlowNode
   */
  source?: NodeSource;
  /**
   *
   * @type {{ [key: string]: any; }}
   * @memberof FlowNode
   */
  inputs?: { [key: string]: any } | undefined;
  /**
   *
   * @type {boolean}
   * @memberof FlowNode
   */
  use_variants?: boolean;
  /**
   *
   * @type {string}
   * @memberof FlowNode
   */
  comment?: string | undefined;
  /**
   *
   * @type {Activate}
   * @memberof FlowNode
   */
  activate?: Activate;
  /**
   *
   * @type {string}
   * @memberof FlowNode
   */
  api?: string | undefined;
  /**
   *
   * @type {string}
   * @memberof FlowNode
   */
  provider?: string | undefined;
  /**
   *
   * @type {string}
   * @memberof FlowNode
   */
  connection?: string | undefined;
  /**
   *
   * @type {string}
   * @memberof FlowNode
   */
  module?: string | undefined;
  /**
   *
   * @type {boolean}
   * @memberof FlowNode
   */
  aggregation?: boolean;
}