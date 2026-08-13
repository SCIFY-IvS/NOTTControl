/*
 * Generated 3/2/2023 9:43:55 AM
 * Copyright (C) 2023
 */
module TcHmi {
    export module Controls {
        export module cryo_framework {
			export class led extends TcHmi.Controls.System.TcHmiControl {

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
                protected __elementOffLedColor!: JQuery;
                protected __elementOnLedColor!: JQuery;

                /* TcHmiControls references: __control{VarName} */

                /* Attribute Variables __attr{VarName} */
                protected __attrEnabled: boolean | undefined;
                protected __attrBlink: boolean | undefined;
                protected __attrOnColor: SolidColor | undefined;
                protected __attrOffColor: SolidColor | undefined;

                /* Internal variables for control logic __{VarName} */

                /* Constants frot he class */

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
                    this.__elementTemplateRoot = this.__element.find('.TcHmi_Controls_cryo_framework_led-Template');
                    if (this.__elementTemplateRoot.length === 0) {
                        throw new Error('Invalid Template.html');
                    }

                    // fetch led color circle
                    this.__elementOffLedColor = this.__elementTemplateRoot.find('.TcHmi_Controls_cryo_framework_led-Template-svg-off-fillcolor');
                    if (this.__elementOffLedColor.length === 0) {
                        throw new Error('Invalid Template.htmml -> Missing Svg Off-Led');
                    }

                    // fetch led color circle
                    this.__elementOnLedColor = this.__elementTemplateRoot.find('.TcHmi_Controls_cryo_framework_led-Template-svg-on-fillcolor');
                    if (this.__elementOnLedColor.length === 0) {
                        throw new Error('Invalid Template.htmml -> Missing Svg On-Led');
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

                /**************** Attributes Setters and Getters ****************/
                /**
                * @description Setter function for 'data-tchmi-led-state' attribute.
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
                    this.__processLedState();
                }

                /**
                * @description Getter function for 'data-tchmi-led-enabled' attribute.
                */
                public getEnabled(): boolean | undefined {
                    return this.__attrEnabled;
                }

                /**
                * @description Setter function for 'data-tchmi-led-blink' attribute.
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
                    this.__processLedState();
                }

                /**
                * @description Getter function for 'data-tchmi-led-blink' attribute.
                */
                public getBlink(): boolean | undefined {
                    return this.__attrBlink;
                }

                /**
                * @description Setter function for 'data-tchmi-led-on-color' attribute.
                * @param valueNew the new value or null 
                */
                public setOnColor(valueNew: SolidColor | null): void {
                    // convert the value with the value converter, in this case we convert
                    // using the schema
                    var schema = TcHmi.Type.getSchema('tchmi:framework#/definitions/SolidColor');
                    let convertedValue = TcHmi.ValueConverter.toSchemaType(valueNew, schema)

                    // check if the converted value is valid
                    if (convertedValue === null) {
                        // if we have no value to set we have to fall back to the defaultValueInternal from description.json
                        convertedValue = this.getAttributeDefaultValueInternal('OnColor') as SolidColor;
                    }

                    // This will work according to this: 
                    // https://infosys.beckhoff.com/english.php?content=../content/1033/te2000_tc3_hmi_engineering/3732102795.html&id=2965886901660953104
                    if (tchmi_equal(convertedValue, this.__attrOnColor)) {
                        // skip processing when the value has not changed
                        return;
                    }

                    // remember the new value
                    this.__attrOnColor = convertedValue;

                    // inform the system that the function has a changed result.
                    TcHmi.EventProvider.raise(this.getId() + '.onPropertyChanged', { propertyName: 'OnColor' });

                    // call process function to process the new value
                    this.__processLedState();
                }

                /**
                * @description Getter function for  'data-tchmi-led-on-color' attribute.
                */
                public getOnColor(): SolidColor | null | undefined {
                    return this.__attrOnColor;
                }

                /**
                * @description Setter function for 'data-tchmi-led-on-color' attribute.
                * @param valueNew the new value or null 
                */
                public setOffColor(valueNew: SolidColor | null): void {
                    // convert the value with the value converter, in this case we convert
                    // using the schema
                    var schema = TcHmi.Type.getSchema('tchmi:framework#/definitions/SolidColor');
                    let convertedValue = TcHmi.ValueConverter.toSchemaType(valueNew, schema)

                    // check if the converted value is valid
                    if (convertedValue === null) {
                        // if we have no value to set we have to fall back to the defaultValueInternal from description.json
                        convertedValue = this.getAttributeDefaultValueInternal('OffColor') as SolidColor;
                    }

                    // This will work according to this: 
                    // https://infosys.beckhoff.com/english.php?content=../content/1033/te2000_tc3_hmi_engineering/3732102795.html&id=2965886901660953104
                    if (tchmi_equal(convertedValue, this.__attrOffColor)) {
                        // skip processing when the value has not changed
                        return;
                    }

                    // remember the new value
                    this.__attrOffColor = convertedValue;

                    // inform the system that the function has a changed result.
                    TcHmi.EventProvider.raise(this.getId() + '.onPropertyChanged', { propertyName: 'OffColor' });

                    // call process function to process the new value
                    this.__processLedState();
                }

                /**
                * @description Getter function for  'data-tchmi-led-on-color' attribute.
                */
                public getOffColor(): SolidColor | null | undefined {
                    return this.__attrOffColor;
                }

                /**************** Processors ****************/
                protected __processLedState(): void {
                    TcHmi.StyleProvider.processFillColor(this.__elementOnLedColor, this.__attrOnColor);
                    TcHmi.StyleProvider.processFillColor(this.__elementOffLedColor, this.__attrOffColor);

                    if (this.__attrEnabled) {
                        if (this.__attrBlink) {
                            this.__elementOnLedColor.addClass("TcHmi_Controls_cryo_framework_led-blink");
                        } else {
                            this.__elementOnLedColor.removeClass("TcHmi_Controls_cryo_framework_led-blink");
                        }
                        this.__elementOnLedColor.attr('opacity', 1);
                    } else {
                        this.__elementOnLedColor.attr('opacity', 0);
                    }
                }
            }
        }
    }
}

/**
* Register Control
*/
TcHmi.Controls.registerEx('led', 'TcHmi.Controls.cryo_framework', TcHmi.Controls.cryo_framework.led);
