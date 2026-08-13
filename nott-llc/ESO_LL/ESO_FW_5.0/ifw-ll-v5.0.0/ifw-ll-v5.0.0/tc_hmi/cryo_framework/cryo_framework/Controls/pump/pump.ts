/*
 * Generated 3/1/2023 5:01:10 PM
 * Copyright (C) 2023
 */
module TcHmi {
    export module Controls {
        export module cryo_framework {
			export class pump extends TcHmi.Controls.System.TcHmiControl {

                /*
                Attribute philosophy
                --------------------
                - Local variables are not set while definition in class, so they have the value 'undefined'.
                - On compile the Framework sets the value from HTML or from theme (possibly 'null') via normal setters.
                - The "changed detection" in the setter will result in processing the value only once while compile.
                - Attention: If we have a Server Binding on an Attribute the setter will be called once with null to initialize and later with the correct value.
                */

                /* HTML Elements __element{VarName} */
                protected __elementTemplateRoot!: JQuery;
                protected __elementPumpCircleOnSvg!: JQuery;
                protected __elementPumpCircleOffSvg!: JQuery;
                protected __elementPumpDirectionSvg!: JQuery;

                /* TcHmiControls references: __control{VarName} */

                /* Attribute Variables __attr{VarName} */
                protected __attrEnabled: boolean;
                protected __attrBlink: boolean | undefined;
                protected __attrDirection: string;
                protected __attrEnabledBackgroundColor: SolidColor | undefined;
                protected __attrDisabledBackgroundColor: SolidColor | undefined;

                /* Internal variables for control logic __{VarName} */
                /* Class constants (readonly) {CONST_NAME} */
                /**
                 * Record type to convert a direction to the correct angle in method `__processPumpState`
                 */
                protected readonly DIRECTIONS: Record<string, number> = {
                    "Up": 3,
                    "Right": 0,
                    "Left": 2,
                    "Down": 1
                };
                /* Event Handlers: mostly destructors __destroy{VarName} */


                /**
                 * Constructor of the control
                 * @param {JQuery} element Element from HTML (internal, do not use)
                 * @param {JQuery} pcElement precompiled Element (internal, do not use)
                 * @param {TcHmi.Controls.ControlAttributeList} attrs Attributes defined in HTML in a special format (internal, do not use)
                 * @returns {void}
                 */
                constructor(element: JQuery, pcElement: JQuery, attrs: TcHmi.Controls.ControlAttributeList) {
                    /** Call base class constructor */
                    super(element, pcElement, attrs);
                }

				/**
                  * If raised, the control object exists in control cache and constructor of each inheritation level was called.
                  * Call attribute processor functions here to initialize default values!
                  */
                public __previnit() {
                    // Fetch template root element
                    this.__elementTemplateRoot = this.__element.find('.TcHmi_Controls_cryo_framework_pump-Template');
                    if (this.__elementTemplateRoot.length === 0) {
                        throw new Error('Invalid Template.html');
                    }

                    // Fetch Svg Drawing Elements
                    this.__elementPumpCircleOnSvg = this.__elementTemplateRoot.find('.TcHmi_Controls_cryo_framework_pump-Template-svg1_pump_circle-on');
                    if (this.__elementPumpCircleOnSvg.length === 0) {
                        throw new Error('Invalid Template.htmml -> Missing On Svg Circle');
                    }

                    // Fetch Svg Drawing Elements
                    this.__elementPumpCircleOffSvg = this.__elementTemplateRoot.find('.TcHmi_Controls_cryo_framework_pump-Template-svg1_pump_circle-off');
                    if (this.__elementPumpCircleOffSvg.length === 0) {
                        throw new Error('Invalid Template.htmml -> Missing Off Svg Circle');
                    }

                    this.__elementPumpDirectionSvg = this.__elementTemplateRoot.find('.TcHmi_Controls_cryo_framework_pump-Template-svg1_pump_direction');
                    if (this.__elementPumpDirectionSvg.length === 0) {
                        throw new Error('Invalid Template.htmml -> Missing Svg Direction Lines');
                    }
                    // Call __previnit of base class
                    super.__previnit();
                }

                /** 
                 * Is called during control initialize phase after attribute setter have been called based on it's default or initial html dom values. 
                 * @returns {void}
                 */
                public __init() {
                    super.__init();
                }

                /**
                * Is called by the system after the control instance gets part of the current DOM.
                * Is only allowed to be called from the framework itself!
                */
                public __attach() {
                    super.__attach();

                    /**
                     * Initialize everything which is only available while the control is part of the active dom.
                     */
                }

                /**
                * Is called by the system after the control instance is no longer part of the current DOM.
                * Is only allowed to be called from the framework itself!
                */
                public __detach() {
                    super.__detach();

                    /**
                     * Disable everything which is not needed while the control is not part of the active dom.
                     * No need to listen to events for example!
                     */
                }

                /**
                * Destroy the current control instance. 
                * Will be called automatically if system destroys control!
                */
                public destroy() {
                    /**
                    * While __keepAlive is set to true control must not be destroyed.
                    */
                    if (this.__keepAlive) {
                        return;
                    }

                    super.destroy();

                    /**
                    * Free resources like child controls etc.
                    */
                }
                
                /**************** Methods ***************************************/
                /* NOTHING HERE */


                /**************** Attributes Setters and Getters ****************/
                /**
                * @description Setter function for 'data-tchmi-pump-enabled' attribute.
                * @param valueNew the new value or null 
                */
                public setEnabled(valueNew: boolean | null): void {
                    // convert the value with the value converter
                    let convertedValue = TcHmi.ValueConverter.toBoolean(valueNew);

                    // check if the converted value is valid
                    if (convertedValue === null) {
                        // if we have no value to set we have to fall back to the defaultValueInternal from description.json
                        convertedValue = this.getAttributeDefaultValueInternal('Enabled') as boolean;
                    }

                    if (tchmi_equal(convertedValue, this.__attrEnabled)) {
                        // skip processing when the value has not changed
                        return;
                    }

                    // remember the new value
                    this.__attrEnabled = convertedValue;

                    // inform the system that the function has a changed result.
                    TcHmi.EventProvider.raise(this.getId() + '.onPropertyChanged', { propertyName: 'Enabled' });

                    // call process function to process the new value
                    this.__processPumpState();
                }

                /**
                * @description Getter function for 'data-tchmi-pump-enabled' attribute.
                */
                public getEnabled(): boolean {
                    return this.__attrEnabled;
                }

                /**
                * @description Setter function for 'data-tchmi-pump-blink' attribute.
                * @param valueNew the new value or null 
                */
                public setBlink(valueNew: boolean | null): void {
                    // convert the value with the value converter
                    let convertedValue = TcHmi.ValueConverter.toBoolean(valueNew);

                    // check if the converted value is valid
                    if (convertedValue === null) {
                        // if we have no value to set we have to fall back to the defaultValueInternal from description.json
                        convertedValue = this.getAttributeDefaultValueInternal('Blink') as boolean;
                    }

                    if (tchmi_equal(convertedValue, this.__attrBlink)) {
                        // skip processing when the value has not changed
                        return;
                    }

                    // remember the new value
                    this.__attrBlink = convertedValue;

                    // inform the system that the function has a changed result.
                    TcHmi.EventProvider.raise(this.getId() + '.onPropertyChanged', { propertyName: 'Blink' });

                    // call process function to process the new value
                    this.__processPumpState();
                }

                /**
                * @description Getter function for 'data-tchmi-pump-blink' attribute.
                */
                public getBlink(): boolean | undefined {
                    return this.__attrBlink;
                }

                /**
                * @description Setter function for 'data-tchmi-pump-direction' attribute.
                * @param valueNew the new value or null 
                */
                public setDirection(valueNew: string | null): void {
                    // convert the value with the value converter
                    let convertedValue = TcHmi.ValueConverter.toString(valueNew);

                    // check if the converted value is valid
                    if (convertedValue === null) {
                        // if we have no value to set we have to fall back to the defaultValueInternal from description.json
                        convertedValue = this.getAttributeDefaultValueInternal('Direction') as string;
                    }

                    if (tchmi_equal(convertedValue, this.__attrDirection)) {
                        // skip processing when the value has not changed
                        return;
                    }

                    // remember the new value
                    this.__attrDirection = convertedValue;

                    // inform the system that the function has a changed result.
                    TcHmi.EventProvider.raise(this.getId() + '.onPropertyChanged', { propertyName: 'Direction' });

                    // call process function to process the new value
                    this.__processPumpState();
                }

                /**
                * @description Getter function for 'data-tchmi-pump-rotation' attribute.
                */
                public getDirection(): string {
                    return this.__attrDirection;
                }

                /**
                * @description Setter function for 'data-tchmi-pump-enabled-background-color' attribute.
                * @param valueNew the new value or null 
                */
                public setEnabledBackgroundColor(valueNew: SolidColor | null): void {
                    // convert the value with the value converter
                    var schema = TcHmi.Type.getSchema('tchmi:framework#/definitions/SolidColor');
                    let convertedValue = TcHmi.ValueConverter.toSchemaType(valueNew, schema)


                    //let convertedValue = TcHmi.ValueConverter.toNumber(valueNew);



                    // check if the converted value is valid
                    if (convertedValue === null) {
                        // if we have no value to set we have to fall back to the defaultValueInternal from description.json
                        convertedValue = this.getAttributeDefaultValueInternal('EnabledBackgroundColor') as SolidColor;
                    }

                    // This will work according to this: 
                    // https://infosys.beckhoff.com/english.php?content=../content/1033/te2000_tc3_hmi_engineering/3732102795.html&id=2965886901660953104
                    if (tchmi_equal(convertedValue, this.__attrEnabledBackgroundColor)) {
                        // skip processing when the value has not changed
                        return;
                    }

                    // remember the new value
                    this.__attrEnabledBackgroundColor = convertedValue;

                    // inform the system that the function has a changed result.
                    TcHmi.EventProvider.raise(this.getId() + '.onPropertyChanged', { propertyName: 'EnabledBackgroundColor' });

                    // call process function to process the new value
                    this.__processPumpState();
                }

                /**
                * @description Getter function for 'data-tchmi-pump-enabled-background-color' attribute.
                */
                public getEnabledBackgroundColor(): SolidColor | null | undefined {
                    return this.__attrEnabledBackgroundColor;
                }


                /**
                * @description Setter function for 'data-tchmi-pump-enabled-background-color' attribute.
                * @param valueNew the new value or null 
                */
                public setDisabledBackgroundColor(valueNew: SolidColor | null): void {
                    // convert the value with the value converter
                    var schema = TcHmi.Type.getSchema('tchmi:framework#/definitions/SolidColor');
                    let convertedValue = TcHmi.ValueConverter.toSchemaType(valueNew, schema)


                    //let convertedValue = TcHmi.ValueConverter.toNumber(valueNew);



                    // check if the converted value is valid
                    if (convertedValue === null) {
                        // if we have no value to set we have to fall back to the defaultValueInternal from description.json
                        convertedValue = this.getAttributeDefaultValueInternal('DisabledBackgroundColor') as SolidColor;
                    }

                    // This will work according to this: 
                    // https://infosys.beckhoff.com/english.php?content=../content/1033/te2000_tc3_hmi_engineering/3732102795.html&id=2965886901660953104
                    if (tchmi_equal(convertedValue, this.__attrDisabledBackgroundColor)) {
                        // skip processing when the value has not changed
                        return;
                    }

                    // remember the new value
                    this.__attrDisabledBackgroundColor = convertedValue;

                    // inform the system that the function has a changed result.
                    TcHmi.EventProvider.raise(this.getId() + '.onPropertyChanged', { propertyName: 'DisabledBackgroundColor' });

                    // call process function to process the new value
                    this.__processPumpState();
                }

                /**
                * @description Getter function for 'data-tchmi-pump-enabled-background-color' attribute.
                */
                public getDisabledBackgroundColor(): SolidColor | null | undefined {
                    return this.__attrDisabledBackgroundColor;
                }

                /**************** Processors ************************************/
                protected __processPumpState(): void {                
                    var pumpDirection: number = 0;
                    if (this.DIRECTIONS[this.__attrDirection] !== undefined) {
                        pumpDirection = this.DIRECTIONS[this.__attrDirection];
                        TcHmi.StyleProvider.processTransform(this.__elementPumpDirectionSvg, 
                            [
                                {
                                    transformType: 'Origin',
                                    x: 50,
                                    xUnit: '%',
                                    y: 50,
                                    yUnit: '%'
                                },
                                {
                                    transformType: 'Rotate',
                                    angle: 90 * pumpDirection
                                }
                            ]
                        );
                    }

                    TcHmi.StyleProvider.processFillColor(this.__elementPumpCircleOnSvg, this.__attrEnabledBackgroundColor);
                    TcHmi.StyleProvider.processFillColor(this.__elementPumpCircleOffSvg, this.__attrDisabledBackgroundColor);
                    
                    if (this.__attrEnabled) {
                        if (this.__attrBlink) {
                            this.__elementPumpCircleOnSvg.addClass("TcHmi_Controls_cryo_framework_pump-blink");
                        } else {
                            this.__elementPumpCircleOnSvg.removeClass("TcHmi_Controls_cryo_framework_pump-blink");
                        }
                        this.__elementPumpCircleOnSvg.attr('opacity', 1);
                    } else {
                        this.__elementPumpCircleOnSvg.attr('opacity', 0);
                    }
                }

            }
        }
    }
}

/**
* Register Control
*/
TcHmi.Controls.registerEx('pump', 'TcHmi.Controls.cryo_framework', TcHmi.Controls.cryo_framework.pump);
