/*
 * Generated 3/1/2023 6:09:58 PM
 * Copyright (C) 2023
 */
module TcHmi {
    export module Controls {
        export module cryo_framework {
			export class signalbox extends TcHmi.Controls.System.TcHmiControl {

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


               /* TcHmiControls references: __control{VarName} */
               protected __controlMainRectangle: TcHmi.Controls.Beckhoff.TcHmiRectangle | undefined;
               protected __controlCornerRectangle: TcHmi.Controls.Beckhoff.TcHmiRectangle | undefined;
               protected __controlSignalText!: TcHmi.Controls.Beckhoff.TcHmiTextblock | undefined;
               protected __controlMainContainer: TcHmi.Controls.System.TcHmiContainer | undefined;

               /* Attribute Variables __attr{VarName} */
               protected __attrAlarmState: boolean | undefined;
               protected __attrWarningState: boolean | undefined;
               protected __attrAlarmColor: SolidColor;
               protected __attrWarningColor: SolidColor;
               protected __attrSignalTextColor: SolidColor;
               protected __attrStrokeThickness: number;
               protected __attrStrokeThicknessUnit: string;
               protected __attrBoxSize: number;
               protected __attrBoxSizeUnit: string;

               /* Internal variables for control logic __{VarName} */

               /* Constants frot he class */
               private readonly WARNING_LETTER: string = 'W';
               private readonly ALARM_LETTER: string = 'A';

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
                    this.__elementTemplateRoot = this.__element.find('.TcHmi_Controls_cryo_framework_signalbox-Template');
                    if (this.__elementTemplateRoot.length === 0) {
                        throw new Error('Invalid Template.html');
                    }

                    // Fetch the Container
                    this.__controlMainContainer = TcHmi.Controls.get<TcHmi.Controls.System.TcHmiContainer>(
                        this.getId() + '_con_Signal_Container'
                    );
                    if (this.__controlMainContainer === undefined) {
                        throw new Error('Invalid Template.html-> Missing Main Container');
                    }

                    // Fetch the Main TcHmiRectangle
                    this.__controlMainRectangle = TcHmi.Controls.get<TcHmi.Controls.Beckhoff.TcHmiRectangle>(
                        this.getId() + '_rec_Signalbox_Main'
                    );
                    if (this.__controlMainRectangle === undefined) {
                        throw new Error('Invalid Template.html-> Missing Main Rectangle drawing');
                    }

                    // Fetch the Corner Rectanble
                    this.__controlCornerRectangle = TcHmi.Controls.get<TcHmi.Controls.Beckhoff.TcHmiRectangle>(
                        this.getId() + '_rec_Signalbox_Corner'
                    );
                    if (this.__controlCornerRectangle === undefined) {
                        throw new Error('Invalid Template.html-> Missing Corner Rectangle drawing');
                    }

                    // Fetch the Corner Rectanble
                    this.__controlSignalText = TcHmi.Controls.get<TcHmi.Controls.Beckhoff.TcHmiTextblock>(
                        this.getId() + '_tex_Signalbox_ActiveSignal'
                    );
                    if (this.__controlSignalText === undefined) {
                        throw new Error('Invalid Template.html-> Missing Active Signal Text');
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
                * @description Setter function for 'data-tchmi-signalbox-alarm' attribute.
                * @param valueNew the new value or null 
                */
                public setAlarmState(valueNew: boolean | null): void {
                    // convert the value with the value converter
                    let convertedValue = TcHmi.ValueConverter.toBoolean(valueNew);

                    // check if the converted value is valid
                    if (convertedValue === null) {
                        // if we have no value to set we have to fall back to the defaultValueInternal from description.json
                        convertedValue = this.getAttributeDefaultValueInternal('AlarmState') as boolean;
                    }

                    if (tchmi_equal(convertedValue, this.__attrAlarmState)) {
                        // skip processing when the value has not changed
                        return;
                    }

                    // remember the new value
                    this.__attrAlarmState = convertedValue;

                    // inform the system that the function has a changed result.
                    TcHmi.EventProvider.raise(this.getId() + '.onPropertyChanged', { propertyName: 'AlarmState' });

                    // call process function to process the new value
                    this.__processAlarmAndWarningSignals();
                }

                /**
                * @description Getter function for 'data-tchmi-signalbox-alarm' attribute.
                */
                public getAlarmState(): boolean | undefined {
                    return this.__attrAlarmState;
                }

                /**
                * @description Setter function for 'data-tchmi-signalbox-alarm' attribute.
                * @param valueNew the new value or null 
                */
                public setWarningState(valueNew: boolean | null): void {
                    // convert the value with the value converter
                    let convertedValue = TcHmi.ValueConverter.toBoolean(valueNew);

                    // check if the converted value is valid
                    if (convertedValue === null) {
                        // if we have no value to set we have to fall back to the defaultValueInternal from description.json
                        convertedValue = this.getAttributeDefaultValueInternal('WarningState') as boolean;
                    }

                    if (tchmi_equal(convertedValue, this.__attrWarningState)) {
                        // skip processing when the value has not changed
                        return;
                    }

                    // remember the new value
                    this.__attrWarningState = convertedValue;

                    // inform the system that the function has a changed result.
                    TcHmi.EventProvider.raise(this.getId() + '.onPropertyChanged', { propertyName: 'WarningState' });

                    // call process function to process the new value
                    this.__processAlarmAndWarningSignals();
                }

                /**
                * @description Getter function for 'data-tchmi-signalbox-alarm' attribute.
                */
                public getWarningState(): boolean | undefined {
                    return this.__attrWarningState;
                }

                /**
                * @description Setter function for 'data-tchmi-signalbox-alarm-color' attribute.
                * @param valueNew the new value or null 
                */
                public setAlarmColor(valueNew: SolidColor | null): void {
                    // convert the value with the value converter, in this case we convert
                    // using the schema
                    var schema = TcHmi.Type.getSchema('tchmi:framework#/definitions/SolidColor');
                    let convertedValue = TcHmi.ValueConverter.toSchemaType(valueNew, schema)

                    // check if the converted value is valid
                    if (convertedValue === null) {
                        // if we have no value to set we have to fall back to the defaultValueInternal from description.json
                        convertedValue = this.getAttributeDefaultValueInternal('AlarmColor') as SolidColor;
                    }

                    // This will work according to this: 
                    // https://infosys.beckhoff.com/english.php?content=../content/1033/te2000_tc3_hmi_engineering/3732102795.html&id=2965886901660953104
                    if (tchmi_equal(convertedValue, this.__attrAlarmColor)) {
                        // skip processing when the value has not changed
                        return;
                    }

                    // remember the new value
                    this.__attrAlarmColor = convertedValue;

                    // inform the system that the function has a changed result.
                    TcHmi.EventProvider.raise(this.getId() + '.onPropertyChanged', { propertyName: 'AlarmColor' });

                    // call process function to process the new value
                    this.__processAlarmAndWarningSignals();
                }

                /**
                * @description Getter function for  'data-tchmi-signalbox-alarm-color' attribute.
                */
                public getAlarmColor(): SolidColor | null | undefined {
                    return this.__attrAlarmColor;
                }

                /**
                * @description Setter function for 'data-tchmi-signalbox-warning-color' attribute.
                * @param valueNew the new value or null 
                */
                public setWarningColor(valueNew: SolidColor | null): void {
                    // convert the value with the value converter, in this case we convert
                    // using the schema
                    var schema = TcHmi.Type.getSchema('tchmi:framework#/definitions/SolidColor');
                    let convertedValue = TcHmi.ValueConverter.toSchemaType(valueNew, schema)

                    // check if the converted value is valid
                    if (convertedValue === null) {
                        // if we have no value to set we have to fall back to the defaultValueInternal from description.json
                        convertedValue = this.getAttributeDefaultValueInternal('WarningColor') as SolidColor;
                    }

                    // This will work according to this: 
                    // https://infosys.beckhoff.com/english.php?content=../content/1033/te2000_tc3_hmi_engineering/3732102795.html&id=2965886901660953104
                    if (tchmi_equal(convertedValue, this.__attrWarningColor)) {
                        // skip processing when the value has not changed
                        return;
                    }

                    // remember the new value
                    this.__attrWarningColor = convertedValue;

                    // inform the system that the function has a changed result.
                    TcHmi.EventProvider.raise(this.getId() + '.onPropertyChanged', { propertyName: 'WarningColor' });

                    // call process function to process the new value
                    this.__processAlarmAndWarningSignals();
                }

                /**
                * @description Getter function for  'data-tchmi-signalbox-warning-color' attribute.
                */
                public getWarningColor(): SolidColor | null | undefined {
                    return this.__attrWarningColor;
                }

                /**
                * @description Setter function for 'data-tchmi-signalbox-text-color' attribute.
                * @param valueNew the new value or null 
                */
                public setSignalTextColor(valueNew: SolidColor | null): void {
                    // convert the value with the value converter, in this case we convert
                    // using the schema
                    var schema = TcHmi.Type.getSchema('tchmi:framework#/definitions/SolidColor');
                    let convertedValue = TcHmi.ValueConverter.toSchemaType(valueNew, schema)

                    // check if the converted value is valid
                    if (convertedValue === null) {
                        // if we have no value to set we have to fall back to the defaultValueInternal from description.json
                        convertedValue = this.getAttributeDefaultValueInternal('SignalTextColor') as Color;
                    }

                    // This will work according to this: 
                    // https://infosys.beckhoff.com/english.php?content=../content/1033/te2000_tc3_hmi_engineering/3732102795.html&id=2965886901660953104
                    if (tchmi_equal(convertedValue, this.__attrSignalTextColor)) {
                        // skip processing when the value has not changed
                        return;
                    }

                    // remember the new value
                    this.__attrSignalTextColor = convertedValue;

                    // inform the system that the function has a changed result.
                    TcHmi.EventProvider.raise(this.getId() + '.onPropertyChanged', { propertyName: 'SignalTextColor' });

                    // call process function to process the new value
                    this.__processAlarmAndWarningSignals();
                }

                /**
                * @description Getter function for  'data-tchmi-signalbox-text-color' attribute.
                */
                public getSignalTextColor(): SolidColor | null | undefined {
                    return this.__attrSignalTextColor;
                }

                /**
                * @description Setter function for 'data-tchmi-signalbox-stroke-thickness' attribute.
                * @param valueNew the new value or null 
                */
                public setBoxStrokeThickness(valueNew: number | null): void {
                    // convert the value with the value converter, in this case we convert
                    // using the schema
                    var schema = TcHmi.Type.getSchema('tchmi:framework#/definitions/MeasurementValue');
                    let convertedValue = TcHmi.ValueConverter.toSchemaType(valueNew, schema)

                    // check if the converted value is valid
                    if (convertedValue === null) {
                        // if we have no value to set we have to fall back to the defaultValueInternal from description.json
                        convertedValue = this.getAttributeDefaultValueInternal('BoxStrokeThickness') as number;
                    }

                    // This will work according to this: 
                    // https://infosys.beckhoff.com/english.php?content=../content/1033/te2000_tc3_hmi_engineering/3732102795.html&id=2965886901660953104
                    if (tchmi_equal(convertedValue, this.__attrStrokeThickness)) {
                        // skip processing when the value has not changed
                        return;
                    }

                    // remember the new value
                    this.__attrStrokeThickness = convertedValue;

                    // inform the system that the function has a changed result.
                    TcHmi.EventProvider.raise(this.getId() + '.onPropertyChanged', { propertyName: 'BoxStrokeThickness' });

                    // call process function to process the new value
                    this.__processAlarmAndWarningSignals();
                }

                /**
                * @description Getter function for  'data-tchmi-signalbox-stroke-thickness' attribute.
                */
                public getBoxStrokeThickness(): number | null | undefined {
                    return this.__attrStrokeThickness;
                }

                /**
                * @description Setter function for 'data-tchmi-signalbox-stroke-thickness-unit' attribute.
                * @param valueNew the new value or null 
                */
                public setBoxStrokeThicknessUnit(valueNew: string | null): void {
                    // convert the value with the value converter, in this case we convert
                    // using the schema
                    var schema = TcHmi.Type.getSchema('tchmi:framework#/definitions/PixelUnit');
                    let convertedValue = TcHmi.ValueConverter.toSchemaType(valueNew, schema)

                    // check if the converted value is valid
                    if (convertedValue === null) {
                        // if we have no value to set we have to fall back to the defaultValueInternal from description.json
                        convertedValue = this.getAttributeDefaultValueInternal('BoxStrokeThicknessUnit') as number;
                    }

                    // This will work according to this: 
                    // https://infosys.beckhoff.com/english.php?content=../content/1033/te2000_tc3_hmi_engineering/3732102795.html&id=2965886901660953104
                    if (tchmi_equal(convertedValue, this.__attrStrokeThicknessUnit)) {
                        // skip processing when the value has not changed
                        return;
                    }

                    // remember the new value
                    this.__attrStrokeThicknessUnit = convertedValue;

                    // inform the system that the function has a changed result.
                    TcHmi.EventProvider.raise(this.getId() + '.onPropertyChanged', { propertyName: 'BoxStrokeThicknessUnit' });

                    // call process function to process the new value
                    this.__processAlarmAndWarningSignals();
                }

                /**
                * @description Getter function for  'data-tchmi-signalbox-stroke-thickness-unit' attribute.
                */
                public getBoxStrokeThicknessUnit(): string | null | undefined {
                    return this.__attrStrokeThicknessUnit;
                }

                /**
                 * @description Setter function for 'data-tchmi-signalbox-box-size' attribute.
                 * @param valueNew the new value or null 
                 */
                public setBoxSize(valueNew: number | null): void {
                    // convert the value with the value converter, in this case we convert
                    // using the schema
                    var schema = TcHmi.Type.getSchema('tchmi:framework#/definitions/MeasurementValue');
                    let convertedValue = TcHmi.ValueConverter.toSchemaType(valueNew, schema)

                    // check if the converted value is valid
                    if (convertedValue === null) {
                        // if we have no value to set we have to fall back to the defaultValueInternal from description.json
                        convertedValue = this.getAttributeDefaultValueInternal('BoxSize') as number;
                    }

                    // This will work according to this: 
                    // https://infosys.beckhoff.com/english.php?content=../content/1033/te2000_tc3_hmi_engineering/3732102795.html&id=2965886901660953104
                    if (tchmi_equal(convertedValue, this.__attrBoxSize)) {
                        // skip processing when the value has not changed
                        return;
                    }

                    // remember the new value
                    this.__attrBoxSize = convertedValue;

                    // inform the system that the function has a changed result.
                    TcHmi.EventProvider.raise(this.getId() + '.onPropertyChanged', { propertyName: 'BoxSize' });

                    // call process function to process the new value
                    this.__processAlarmAndWarningSignals();
                }

                /**
                * @description Getter function for  'data-tchmi-signalbox-stroke-thickness' attribute.
                */
                public getBoxSize(): number | null | undefined {
                    return this.__attrBoxSize;
                }

                /**
                 * @description Setter function for 'data-tchmi-signalbox-box-size-unit' attribute.
                 * @param valueNew the new value or null 
                 */
                public setBoxSizeUnit(valueNew: string | null): void {
                    // convert the value with the value converter, in this case we convert
                    // using the schema
                    var schema = TcHmi.Type.getSchema('tchmi:framework#/definitions/PixelUnit');
                    let convertedValue = TcHmi.ValueConverter.toSchemaType(valueNew, schema)

                    // check if the converted value is valid
                    if (convertedValue === null) {
                        // if we have no value to set we have to fall back to the defaultValueInternal from description.json
                        convertedValue = this.getAttributeDefaultValueInternal('BoxSizeUnit') as number;
                    }

                    // This will work according to this: 
                    // https://infosys.beckhoff.com/english.php?content=../content/1033/te2000_tc3_hmi_engineering/3732102795.html&id=2965886901660953104
                    if (tchmi_equal(convertedValue, this.__attrBoxSizeUnit)) {
                        // skip processing when the value has not changed
                        return;
                    }

                    // remember the new value
                    this.__attrBoxSizeUnit = convertedValue;

                    // inform the system that the function has a changed result.
                    TcHmi.EventProvider.raise(this.getId() + '.onPropertyChanged', { propertyName: 'BoxSizeUnit' });

                    // call process function to process the new value
                    this.__processAlarmAndWarningSignals();
                }

                /**
                * @description Getter function for  'data-tchmi-signalbox-box-size-unit' attribute.
                */
                public getBoxSizeUnit(): string | null | undefined {
                    return this.__attrBoxSizeUnit;
                }

                /**************** Processors ****************/
                protected __processAlarmAndWarningSignals(): void {
                    this.__controlSignalText?.setTextColor(this.__attrSignalTextColor);
                    this.__controlMainRectangle?.setStrokeThickness(this.__attrStrokeThickness);
                    this.__controlCornerRectangle?.setLeft(this.__attrStrokeThickness);
                    this.__controlCornerRectangle?.setBottom(this.__attrStrokeThickness);
                    this.__controlCornerRectangle?.setWidth(this.__attrBoxSize);
                    this.__controlCornerRectangle?.setHeight(this.__attrBoxSize);
                    
                    //this.__controlSignalText?.setLeft(this.__attrStrokeThickness);
                    //this.__controlSignalText?.setBottom(this.__attrStrokeThickness);
                    this.__controlSignalText?.setWidth(this.__attrBoxSize + this.__attrStrokeThickness);
                    this.__controlSignalText?.setHeight(this.__attrBoxSize + this.__attrStrokeThickness);
                    this.__controlSignalText?.setTextFontSize(this.__attrBoxSize + this.__attrStrokeThickness - 4);
                    
                    if (this.__attrAlarmState == true) {
                        this.__controlMainRectangle?.setStrokeColor(this.__attrAlarmColor);
                        this.__controlCornerRectangle?.setStrokeColor(this.__attrAlarmColor);
                        this.__controlCornerRectangle?.setFillColor(this.__attrAlarmColor);
                        this.__controlSignalText?.setText(this.ALARM_LETTER);
                        this.setOpacity(1);
                        return;
                    } else if (this.__attrWarningState == true) {
                        this.__controlMainRectangle?.setStrokeColor(this.__attrWarningColor);
                        this.__controlCornerRectangle?.setStrokeColor(this.__attrWarningColor);
                        this.__controlCornerRectangle?.setFillColor(this.__attrWarningColor);
                        this.__controlSignalText?.setText(this.WARNING_LETTER);
                        this.setOpacity(1);
                        return;
                    }
                    this.setOpacity(0);
                    return;
                }
            }
        }
    }
}

/**
* Register Control
*/
TcHmi.Controls.registerEx('signalbox', 'TcHmi.Controls.cryo_framework', TcHmi.Controls.cryo_framework.signalbox);
